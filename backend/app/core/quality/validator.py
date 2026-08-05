"""문항 검증 오케스트레이터.

validate_items(items, llm, config) → 입력과 같은 순서의 ItemVerdict 목록.

단계: ① polish(mcq 오답 선별) + 기계 검사 → ② LLM 심판 → ③ 풀이 왕복
     → ④ 불합격분 사유 첨부 수정 1회 → ①~③ 재검사 (수정은 한 번만).

호출자(문제은행 배치·학습 JIT·형성평가)는 이 함수 하나만 안다.
"""
import logging

from app.core.llm.base import LLMClient
from app.core.quality import parsing
from app.core.quality.checks import check_solution, mechanical_check, polish_mcq
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
) -> list[ItemVerdict]:
    """llm = 심판·풀이자 (교차 검증 시 생성과 다른 모델을 넣는다).
    revise_llm = 불합격 수정 담당 (생성 성격이므로 기본은 llm이지만,
    교차 검증 구성에선 생성 모델을 넘기는 게 자연스럽다)."""
    config = config or QualityConfig()
    verdicts = await _screen(items, llm, config)

    if config.enable_revise:
        failed_idx = [i for i, v in enumerate(verdicts) if not v.ok]
        if failed_idx:
            await _revise_and_rescreen(
                items, verdicts, failed_idx, llm, revise_llm or llm, config
            )
    return verdicts


async def _screen(
    items: list[CandidateItem], llm: LLMClient, config: QualityConfig
) -> list[ItemVerdict]:
    """기계 → 심판 → 풀이 순서로 거른다. 싼 검사가 먼저."""
    verdicts: list[ItemVerdict] = []
    for it in items:
        if it.type == "mcq":
            polish_mcq(it.data)
        reason = mechanical_check(it.type, it.data, it.evidence_text)
        verdicts.append(
            ItemVerdict(ok=reason is None, stage="mechanical" if reason else "", reason=reason or "", item=it)
        )

    await _llm_stage(verdicts, llm, config, judge=True)
    if config.enable_solve:
        await _llm_stage(verdicts, llm, config, judge=False)
    return verdicts


async def _llm_stage(
    verdicts: list[ItemVerdict], llm: LLMClient, config: QualityConfig, judge: bool
) -> None:
    """생존 문항만 묶어 심판(judge=True) 또는 풀이자(judge=False) 콜."""
    survivors = [
        i
        for i, v in enumerate(verdicts)
        if v.ok and (judge or v.item.type in config.solve_types)
    ]
    for start in range(0, len(survivors), config.batch_size):
        idx_batch = survivors[start : start + config.batch_size]
        batch = [verdicts[i].item for i in idx_batch]
        if judge:
            raw = await llm.generate(build_judge_prompt(batch))
            results = parsing.parse_verdicts(raw, len(batch))
            for i, (ok, reason) in zip(idx_batch, results):
                if not ok:
                    verdicts[i] = ItemVerdict(
                        ok=False, stage="judge", reason=reason, item=verdicts[i].item,
                        revised=verdicts[i].revised,
                    )
        else:
            raw = await llm.generate(build_solve_prompt(batch))
            answers = parsing.parse_solutions(raw, len(batch))
            for i, answer in zip(idx_batch, answers):
                it = verdicts[i].item
                reason = check_solution(it.type, it.data, answer)
                if reason:
                    verdicts[i] = ItemVerdict(
                        ok=False, stage="solve", reason=reason, item=it,
                        revised=verdicts[i].revised,
                    )


async def _revise_and_rescreen(
    items: list[CandidateItem],
    verdicts: list[ItemVerdict],
    failed_idx: list[int],
    llm: LLMClient,
    revise_llm: LLMClient,
    config: QualityConfig,
) -> None:
    """불합격 문항을 사유와 함께 수정시키고(revise_llm), 재검사는 llm이 한다."""
    for start in range(0, len(failed_idx), config.batch_size):
        idx_batch = failed_idx[start : start + config.batch_size]
        failed_items = [items[i] for i in idx_batch]
        reasons = [verdicts[i].reason for i in idx_batch]

        raw = await revise_llm.generate(build_revision_prompt(failed_items, reasons))
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
        rescreened = await _screen(retry_items, llm, no_revise)
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
