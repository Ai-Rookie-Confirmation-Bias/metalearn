"""문항 검증 오케스트레이터.

validate_items(items, llm, config) → 입력과 같은 순서의 ItemVerdict 목록.

단계: ① polish(mcq 오답 선별) + 기계 검사 → ② LLM 심판 → ③ 풀이 왕복
     → ④ 불합격분 사유 첨부 수정 1회 → ①~③ 재검사 (수정은 한 번만).

배심원단(second_llm): 심판·풀이를 다른 혈통 모델로 한 번 더 돌린다.
어느 한쪽이 잡으면 탈락, 2차의 판독 불가 응답은 기권(1차 판정 유지) —
2차 모델의 형식 붕괴가 멀쩡한 문항을 학살하지 않게 한다 (K-EXAONE 실측).

호출자(문제은행 배치·학습 JIT·형성평가)는 이 함수 하나만 안다.
"""
import logging

from app.core.config import settings
from app.core.llm.base import LLMClient
from app.core.quality import parsing
from app.core.quality.checks import (
    check_solution,
    mechanical_check,
    polish_mcq,
    scrub_sentence_refs,
)
from app.core.quality.prompts import (
    build_judge_prompt,
    build_revision_prompt,
    build_solve_prompt,
)
from app.core.quality.types import CandidateItem, ItemVerdict, QualityConfig

logger = logging.getLogger(__name__)


async def validate_items(
    items: list[CandidateItem],
    llm: LLMClient,
    config: QualityConfig | None = None,
    revise_llm: LLMClient | None = None,
    second_llm: LLMClient | None = None,
) -> list[ItemVerdict]:
    """llm = 1차 심판·풀이. second_llm = 배심원(있으면 심판·풀이 2차, 기권 허용).
    revise_llm = 불합격 수정 담당 (생성 성격이므로 보통 생성 모델을 넘긴다)."""
    config = config or QualityConfig()
    verdicts = await _screen(items, llm, config, second_llm)

    if config.enable_revise:
        # cloze는 수정 대상에서 제외 — 지문(segments)은 코드가 조립하는 것이라
        # LLM 재작성이 손대면 정답 노출을 재생산한다 (pro3 실측 3건, QUIZ_TUNING §12).
        failed_idx = [
            i for i, v in enumerate(verdicts) if not v.ok and v.item.type != "cloze"
        ]
        if failed_idx:
            await _revise_and_rescreen(
                items, verdicts, failed_idx, llm, revise_llm or llm, config, second_llm
            )
    return verdicts


async def _screen(
    items: list[CandidateItem],
    llm: LLMClient,
    config: QualityConfig,
    second_llm: LLMClient | None = None,
) -> list[ItemVerdict]:
    """기계 → 심판(1차→배심) → 풀이(1차→배심) 순서로 거른다. 싼 검사가 먼저."""
    verdicts: list[ItemVerdict] = []
    for it in items:
        scrub_sentence_refs(it.type, it.data)
        if it.type == "mcq":
            polish_mcq(it.data)
        reason = mechanical_check(it.type, it.data, it.evidence_text)
        verdicts.append(
            ItemVerdict(ok=reason is None, stage="mechanical" if reason else "", reason=reason or "", item=it)
        )

    await _judge_stage(verdicts, llm, config, jury=False)
    if second_llm is not None:
        await _judge_stage(verdicts, second_llm, config, jury=True)
    if config.enable_solve:
        await _solve_stage(verdicts, llm, config, jury=False)
        if second_llm is not None:
            await _solve_stage(verdicts, second_llm, config, jury=True)
    return verdicts


def _fail(verdicts: list[ItemVerdict], i: int, stage: str, reason: str) -> None:
    verdicts[i] = ItemVerdict(
        ok=False, stage=stage, reason=reason, item=verdicts[i].item,
        revised=verdicts[i].revised,
    )


async def _judge_stage(
    verdicts: list[ItemVerdict], llm: LLMClient, config: QualityConfig, jury: bool
) -> None:
    """심판 콜. jury=True(배심원)면 판독 불가는 기권, 사유에 [배심] 태그."""
    survivors = [i for i, v in enumerate(verdicts) if v.ok]
    for start in range(0, len(survivors), config.batch_size):
        idx_batch = survivors[start : start + config.batch_size]
        results = await _call_judge(
            [verdicts[i].item for i in idx_batch], llm, jury
        )
        # 판독 불가만 모아 1회 재질의 — 형식 난조(깨진 JSON)는 문항 결함이
        # 아니므로, 곧장 탈락/기권시키지 않고 다시 물어본다 (재검증 감사 실측:
        # 판독 불가의 상당수가 재질의 한 번에 정상 응답).
        unread = [pos for pos, r in enumerate(results) if r is None]
        if unread:
            retry = await _call_judge(
                [verdicts[idx_batch[pos]].item for pos in unread], llm, jury
            )
            for pos, r in zip(unread, retry):
                results[pos] = r
        for i, res in zip(idx_batch, results):
            if res is None:
                if not jury:  # 단독/1차 심판은 보수적 — 못 읽으면 불합격
                    _fail(verdicts, i, "judge", "심판 응답 파싱 실패 (재질의 포함)")
                continue  # 배심원 기권 — 1차 판정 유지
            ok, reason = res
            if jury and not ok and not reason.strip():
                continue  # 배심의 무사유 불합격 = 판독 불가에 준함 → 기권 (감사 실측 2건)
            if not ok:
                _fail(verdicts, i, "judge", f"[배심] {reason}" if jury else reason)


async def _call_judge(
    batch: list[CandidateItem], llm: LLMClient, jury: bool
) -> list[tuple[bool, str] | None]:
    # json_mode: Solar(pro3)가 배열을 객체 이어붙임으로 답하는 문제를
    # response_format=json_object로 원천 차단. EXAONE 클라이언트는 kwargs를
    # 무시하므로(model 포함) 배심원 콜에는 영향 없다.
    raw = await llm.generate(
        build_judge_prompt(batch, neutral_example=jury),
        model=settings.QUIZ_CHAT_MODEL,
        json_mode=True,
    )
    return parsing.parse_verdicts(raw, len(batch))


async def _solve_stage(
    verdicts: list[ItemVerdict], llm: LLMClient, config: QualityConfig, jury: bool
) -> None:
    """풀이 왕복 콜. jury=True면 무응답은 기권 (모델 형식 난조 ≠ 문항 결함)."""
    survivors = [
        i for i, v in enumerate(verdicts) if v.ok and v.item.type in config.solve_types
    ]
    for start in range(0, len(survivors), config.batch_size):
        idx_batch = survivors[start : start + config.batch_size]
        answers = await _call_solve([verdicts[i].item for i in idx_batch], llm, jury)
        # 판독 불가만 모아 1회 재질의 — 깨진 배치 응답의 형식 난조를 문항
        # 결함으로 처리하지 않는다 (심판 재질의와 같은 원칙)
        unread = [pos for pos, a in enumerate(answers) if a is None]
        if unread:
            retry = await _call_solve(
                [verdicts[idx_batch[pos]].item for pos in unread], llm, jury
            )
            for pos, a in zip(unread, retry):
                answers[pos] = a
        for i, answer in zip(idx_batch, answers):
            if answer is None and jury:
                continue  # 배심원 기권
            it = verdicts[i].item
            reason = check_solution(it.type, it.data, answer)
            if reason:
                _fail(verdicts, i, "solve", f"[배심] {reason}" if jury else reason)


async def _call_solve(batch: list[CandidateItem], llm: LLMClient, jury: bool) -> list:
    raw = await llm.generate(
        build_solve_prompt(batch, neutral_example=jury),
        model=settings.QUIZ_CHAT_MODEL,
        json_mode=True,
    )
    answers = parsing.parse_solutions(raw, len(batch))
    if any(a is None for a in answers):
        # "풀이자 응답 없음"의 원인 추적용 — 어떤 형태로 답했는지 남긴다
        logger.warning(
            "풀이자 응답 일부 판독 불가 (%d/%d) — raw 앞 300자: %r",
            sum(a is None for a in answers), len(batch), raw[:300],
        )
    return answers


async def _revise_and_rescreen(
    items: list[CandidateItem],
    verdicts: list[ItemVerdict],
    failed_idx: list[int],
    llm: LLMClient,
    revise_llm: LLMClient,
    config: QualityConfig,
    second_llm: LLMClient | None = None,
) -> None:
    """불합격 문항을 사유와 함께 수정시키고(revise_llm), 같은 배심원단으로 재검사."""
    for start in range(0, len(failed_idx), config.batch_size):
        idx_batch = failed_idx[start : start + config.batch_size]
        failed_items = [items[i] for i in idx_batch]
        reasons = [verdicts[i].reason for i in idx_batch]

        raw = await revise_llm.generate(
            build_revision_prompt(failed_items, reasons),
            model=settings.QUIZ_CHAT_MODEL,
            json_mode=True,
        )
        revisions = parsing.parse_revisions(raw, len(idx_batch))

        retry_items: list[CandidateItem] = []
        retry_pos: list[int] = []
        for i, revised_data in zip(idx_batch, revisions):
            if revised_data is None:
                continue  # 수정 포기 — 원 판정 유지
            retry_pos.append(i)
            retry_items.append(
                CandidateItem(
                    type=items[i].type, data=revised_data, evidence_text=items[i].evidence_text
                )
            )
        if not retry_items:
            continue

        no_revise = config.model_copy(update={"enable_revise": False})
        rescreened = await _screen(retry_items, llm, no_revise, second_llm)
        for i, verdict in zip(retry_pos, rescreened):
            if verdict.ok:
                verdicts[i] = ItemVerdict(ok=True, revised=True, item=verdict.item)
                logger.info("수정 루프로 회생: %s", items[i].type)
            else:
                verdicts[i] = ItemVerdict(
                    ok=False,
                    stage=verdict.stage,
                    reason=f"수정 후에도 불합격 — {verdict.reason} (원사유: {verdicts[i].reason})",
                    item=verdict.item,
                )
