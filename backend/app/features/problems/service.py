"""[3.Service] 문제 생성 에이전트 오케스트레이션.

원문을 **구간(span) 단위로 쪼개** 구간마다 소량씩 생성하고(spans.py 참조),
반환 JSON을 안전하게 파싱·검증해 유효 문항만 결과에 싣는다.
커버리지는 재시도로 좇는 목표가 아니라 **전 구간을 도는 구조**로 확보한다.
개수 충족/미달은 LLM 자진신고가 아니라 코드가 세어 coverage_note를 만든다.
(DB 적재는 검증 에이전트 통과분만 — v1은 생성·검증(curl)까지.)
"""
import asyncio
import json
import logging

from pydantic import ValidationError

from app.core.llm.base import LLMClient
from app.core.llm.solar import solar_client
from app.features.problems.grounding import (
    answer_stands_out,
    evidence_in_source,
    items_not_in_source,
    normalize,
)
from app.features.problems.prompts import build_pair_prompt, build_span_prompt
from app.features.problems.quality import (
    answer_leaked_in_title,
    is_free_response_style,
    strip_option_label,
)
from app.features.problems import coverage, levels, solve_check, spans
from app.features.problems.schemas import (
    ConceptInput,
    ConceptProblems,
    GenerateProblemsRequest,
    GenerateProblemsResponse,
    Level,
    Problem,
    ProblemType,
)

logger = logging.getLogger(__name__)

_LEVELS: tuple[int, ...] = (1, 2, 3)
# 동시 LLM 호출 수. span 방식은 개념 하나가 구간 수만큼 호출하므로 개념이 아니라
# **호출**을 잠가야 한다. 없으면 자료 하나(개념 22개 × 구간 십수 개)에 수백 개
# 요청이 한꺼번에 나가고, rate limit에 걸리면 **전부** 실패한다.
MAX_CONCURRENT_CALLS = 6
# 구간 하나에서 노릴 문항 수(L1·L2). 크게 잡을수록 수율이 무너진다는 것이
# 볼륨 실측의 결론이므로 작게 유지한다 — 총량은 구간 수가 만든다.
_PER_SPAN = 2


def _extract_json_object(raw: str) -> dict:
    """LLM 응답에서 JSON 객체를 뽑아낸다.

    response_format=json_object여도 코드펜스·잡텍스트가 섞이는 경우를
    방어적으로 처리 (첫 '{' ~ 마지막 '}' 구간 파싱).
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            return json.loads(raw[start : end + 1])
        raise


class _CallStats:
    """개념 하나의 호출 실패 집계.

    coverage_note가 개념별이므로 카운터도 개념별이어야 한다. 서비스 인스턴스에
    두면 병렬로 도는 다른 개념의 실패까지 섞여 들어간다.
    """

    def __init__(self) -> None:
        self.failures = 0


# (문항, 요청 레벨, 출처 구간 index). 구간 index는 슬롯 배분에 쓴다 —
# 어느 구간에서 나왔는지를 잃으면 상한을 걸 때 앞 구간만 남는다. 쌍(L3)은 -1.
_Candidate = tuple[Problem, int, int]


class ProblemGeneratorService:
    def __init__(self, llm: LLMClient | None = None) -> None:
        # 기본은 팀 스택 Solar. LLMClient 계약 뒤라 교체 가능.
        self.llm = llm or solar_client
        # 세마포어는 **호출 단위**로 건다. span 방식에서는 한 개념이 여러 번
        # 호출하므로, 개념 단위로 잠그면 실제 동시 호출 수를 통제하지 못한다.
        # (라우터가 요청마다 인스턴스를 만드므로 이 상한은 요청 단위다.)
        self._sem = asyncio.Semaphore(MAX_CONCURRENT_CALLS)

    async def generate(
        self, req: GenerateProblemsRequest
    ) -> GenerateProblemsResponse:
        results = await asyncio.gather(
            *(
                self._generate_for_concept(req.subject, c, req.per_level)
                for c in req.concepts
            )
        )
        return GenerateProblemsResponse(subject=req.subject, results=list(results))

    async def _ask(
        self, prompt: str, tag: str, stats: "_CallStats"
    ) -> list[dict]:
        """LLM 한 번 호출해 problems 배열만 꺼낸다. 실패는 빈 목록으로 흡수한다.

        구간 하나가 실패해도 나머지 구간은 살아야 하므로 여기서 예외를 막는다
        (개념을 gather로 병렬 처리하던 때와 같은 이유 — 하나가 전체를 죽이면 안 된다).
        """
        async with self._sem:
            try:
                raw = await self.llm.generate(
                    prompt, response_format={"type": "json_object"}, temperature=0.4
                )
                data = _extract_json_object(raw)
            except Exception as exc:  # noqa: BLE001
                logger.warning("%s: 생성 호출 실패 (%s)", tag, type(exc).__name__)
                stats.failures += 1
                return []
        items = data.get("problems")
        return items if isinstance(items, list) else []

    async def _generate_for_concept(
        self, subject: str, concept: ConceptInput, per_level: int
    ) -> ConceptProblems:
        """원문을 구간(span)으로 쪼개 구간마다 소량씩 생성한다.

        구간 하나 → L1·L2(재인·적용), 인접한 두 구간 → L3(비교·종합).
        커버리지가 "잘 되기를 바라는 값"에서 **전 구간을 도는 구조**로 바뀐다.
        문항 수도 숫자로 지정하는 대신 원문 크기에서 나온다(per_level은 상한).

        구간별 호출은 서로 독립이라 전부 병렬로 띄우고, 동시 호출 수는
        _ask의 세마포어가 잡는다.
        """
        stats = _CallStats()
        span_list = spans.split(concept.source_text)
        if not span_list:
            return ConceptProblems(
                concept_id=concept.concept_id,
                title=concept.title,
                chapter_id=concept.chapter_id,
                chapter_title=concept.chapter_title,
                coverage_note="원문에서 출제 가능한 구간을 찾지 못했다.",
            )

        # L1·L2는 구간마다, L3는 같은 표 안의 인접 쌍에서. 쌍 수는 레벨 상한에
        # 맞춰 제한한다(모든 조합을 쓰면 구간 16개에 120쌍이 되어 호출이 폭증한다).
        pairs = spans.pair_indices(span_list, per_level + 1)
        raw_batches = await asyncio.gather(
            *[
                self._ask(
                    build_span_prompt(
                        subject, concept.title, s.heading, s.text, _PER_SPAN
                    ),
                    f"{concept.concept_id}/span{s.index}",
                    stats,
                )
                for s in span_list
            ],
            *[
                self._ask(
                    build_pair_prompt(
                        subject, concept.title, span_list[a].text, span_list[b].text
                    ),
                    f"{concept.concept_id}/pair{a}-{b}",
                    stats,
                )
                for a, b in pairs
            ],
        )

        # 게이트는 그대로 재사용한다 — 생성 방식과 직교하므로 손댈 필요가 없다.
        # 다만 결과를 **구간별로** 나눠 본다: 한 구간이 통째로 비면 그 구간은
        # 커버리지에서 빠지므로, 그 구간만 사유를 실어 다시 시도한다.
        candidates: list[_Candidate] = []
        reasons: list[str] = []
        thin: list[tuple[spans.Span, list[str]]] = []
        for s, batch in zip(span_list, raw_batches[: len(span_list)]):
            ok, why, _ = self._validate_problems(batch, concept)
            candidates.extend((p, lv, s.index) for p, lv in ok)
            reasons.extend(why)
            if not ok and why:
                # 사유가 없는 빈 응답은 "구간이 얇다"는 모델의 판단이므로
                # 재시도해도 같은 답이 온다. 폐기가 있었던 구간만 다시 부른다.
                thin.append((s, why))
        for batch in raw_batches[len(span_list) :]:
            ok, why, _ = self._validate_problems(batch, concept)
            candidates.extend((p, lv, -1) for p, lv in ok)
            reasons.extend(why)

        if thin:
            retry_batches = await asyncio.gather(
                *[
                    self._ask(
                        build_span_prompt(
                            subject,
                            concept.title,
                            s.heading,
                            s.text,
                            1,  # 재시도는 확실한 1문항만 — 욕심이 실패를 부른다
                            feedback=_span_feedback(why),
                        ),
                        f"{concept.concept_id}/span{s.index}·재시도",
                        stats,
                    )
                    for s, why in thin
                ]
            )
            for (s, _), batch in zip(thin, retry_batches):
                ok, why, _ = self._validate_problems(batch, concept)
                candidates.extend((p, lv, s.index) for p, lv in ok)
                reasons.extend(why)

        # [게이트4] 검수는 개념당 배치 1콜 — 구간마다 부르면 호출이 배로 든다.
        if candidates:
            kept, solve_reasons = await solve_check.verify_problems(
                self.llm, [p for p, _, _ in candidates], concept.source_text
            )
            kept_ids = {id(p) for p in kept}
            candidates = [c for c in candidates if id(c[0]) in kept_ids]
            reasons.extend(solve_reasons)

        by_level = _select(candidates, per_level)
        problems = [p for lv in _LEVELS for p in by_level[lv]]
        report = coverage.analyze(_evidences(by_level), concept.source_text)
        note = _coverage_note(
            by_level, per_level, len(reasons), report, stats.failures
        )
        return ConceptProblems(
            concept_id=concept.concept_id,
            title=concept.title,
            chapter_id=concept.chapter_id,
            chapter_title=concept.chapter_title,
            problems=problems,
            coverage_note=f"구간 {len(span_list)}개·쌍 {len(pairs)}개. {note}",
        )

    @staticmethod
    def _validate_problems(
        rawitems: object, concept: ConceptInput
    ) -> tuple[list[Problem], list[str], list[str]]:
        """개별 문항을 검증 — 한 문항이 깨져도 나머지는 살린다.

        게이트: ① Pydantic(정답=보기 일치 등) ② 지문 형식(객관식다움)
        ③ source_evidence 원문 실재. 이후 레벨 라벨이 실제 난이도와 맞는지 보고
        과대 태깅이면 **강등**한다(폐기가 아니다 — 문항 자체는 멀쩡하다).

        반환 (통과 문항, 폐기 사유, 강등 기록). 폐기와 강등을 나눠 돌려주는
        이유는 폐기 수만 세어야 coverage_note의 폐기 집계가 부풀지 않기 때문이다.
        """
        problems: list[tuple[Problem, int]] = []
        reasons: list[str] = []
        downgrades: list[str] = []
        source = concept.source_text
        for item in rawitems if isinstance(rawitems, list) else []:
            try:
                p = Problem.model_validate(_normalize_options(item))
            except ValidationError:
                reasons.append("정답이 보기와 불일치하거나 필드 누락")
                continue
            # 프롬프트로 금지해도 모델이 반복해 어기는 항목은 코드로 확정 차단.
            if is_free_response_style(p.question):
                reasons.append("지문이 서술형('~하시오') — 객관식 선택형이어야 함")
                continue
            # 개념명이 화면에 노출되므로 정답이 제목에 통째로 담기면 유출이다.
            if answer_leaked_in_title(p.answer, concept.title):
                reasons.append("정답이 개념명에 그대로 노출됨(정답 유출)")
                continue
            # 근거가 원문에 실재하는지 기계 확인(자기검증 아님, grounding 모듈).
            if not evidence_in_source(p.source_evidence, source):
                reasons.append("source_evidence가 원문에 없음(창작 의심)")
                continue
            # 근거만 대조하면 **보기의 창작**이 빠져나간다. 순서 배열은 보기 전체가,
            # 다중 정답은 정답 항목이 원문에 실재해야 한다(실측: 원문에 없는 단계를
            # 지어내 배열시킨 문항이 게이트를 통과했다).
            checked = (
                p.options
                if p.type is ProblemType.ORDER
                else p.answer_texts
                if p.type is ProblemType.MULTI
                else []
            )
            if missing := items_not_in_source(checked, source):
                reasons.append(f"보기가 원문에 없음(창작): {', '.join(missing[:2])}")
                continue
            # 정답만 원문에 있고 오답이 전부 창작이면, 원문을 읽은 학습자에게는
            # 내용을 몰라도 답이 보인다(실측: mcq 7문항 중 3문항).
            if answer_stands_out(p.answer_texts, p.options, source):
                reasons.append(
                    "정답만 원문에 있고 오답은 전부 창작 — 원문의 다른 항목으로 오답을 만들 것"
                )
                continue
            # 레벨 과대 태깅은 강등해 살린다. 라벨만 틀렸을 뿐 문항은 쓸 수 있고,
            # 버리면 문항 수만 줄고 재시도를 태운다.
            requested = int(p.level)
            actual = levels.assess(p.type, p.answer, p.source_evidence, source)
            if actual < requested:
                downgrades.append(f"L{requested}로 낸 문항이 실제 L{actual} 수준")
                # model_copy는 검증을 다시 돌리지 않으므로 int를 그대로 넣으면
                # 필드에 생 int가 앉아 직렬화 경고가 난다. Level로 감싼다.
                p = p.model_copy(update={"level": Level(actual)})
            # 요청 레벨을 함께 돌려준다 — 슬롯은 "무엇을 요청했나" 기준으로 세야
            # 강등된 문항이 이미 찬 하위 레벨 슬롯과 경쟁해 버려지지 않는다.
            problems.append((p, requested))
        return problems, reasons, downgrades


def _evidences(by_level: dict[int, list[Problem]]) -> list[str]:
    """누적된 문항의 근거 목록 — 커버리지 계산 입력."""
    return [p.source_evidence for lv in _LEVELS for p in by_level[lv]]


def _normalize_options(item: object) -> object:
    """보기·정답 앞에 LLM이 붙인 자체 라벨("A. ", "1) ")을 제거한다.

    라벨이 남으면 화면에서 "A) A. FIFO"로 겹쳐 보이고, answer와 options의
    글자 일치가 깨져 멀쩡한 문항이 검증에서 폐기된다.
    정답은 유형에 따라 문자열이거나 배열이므로 둘 다 처리한다.
    """
    if not isinstance(item, dict):
        return item
    out = dict(item)
    if isinstance(out.get("options"), list):
        out["options"] = [strip_option_label(str(o)) for o in out["options"]]
    answer = out.get("answer")
    if isinstance(answer, str):
        out["answer"] = strip_option_label(answer)
    elif isinstance(answer, list):
        out["answer"] = [strip_option_label(str(a)) for a in answer]
    return out


def _span_feedback(reasons: list[str]) -> str:
    """한 구간에서 만든 문항이 전부 폐기됐을 때 그 구간에만 주는 지시.

    전체 재생성 대신 실패한 구간만 다시 부르므로 피드백도 그 구간의 사유만 싣는다.
    """
    return (
        "직전 시도에서 이 구간으로 만든 문항이 전부 폐기됐다. 사유: "
        + " / ".join(sorted(set(reasons)))
        + ".\n무리하지 말고, 구간에 그대로 적힌 내용만으로 확실한 1문항만 만들어라."
    )


def _select(candidates: list[_Candidate], per_level: int) -> dict[int, list[Problem]]:
    """레벨별 상한(per_level)을 지키되 슬롯을 구간에 고루 배분한다.

    도착 순서대로 채우면 앞쪽 구간 문항이 슬롯을 다 먹어 원문 뒷부분이 통째로
    빠진다 — 구간 분할의 의미가 사라진다. 그래서 "각 구간의 1번째 문항"을 먼저
    한 바퀴 돌고, 그다음 2번째를 돈다(구간별 라운드로빈).
    """
    ranked: list[tuple[int, Problem, int]] = []
    taken: dict[int, int] = {}
    for p, requested, span_index in candidates:
        rank = taken.get(span_index, 0)
        taken[span_index] = rank + 1
        ranked.append((rank, p, requested))
    ranked.sort(key=lambda t: t[0])  # 안정 정렬 — 같은 바퀴 안에서는 원문 순서

    by_level: dict[int, list[Problem]] = {lv: [] for lv in _LEVELS}
    seen: set[str] = set()
    for _, p, requested in ranked:
        key = normalize(p.question)
        if key in seen:
            continue
        lv = int(p.level)
        # 강등된 문항은 하위 레벨의 목표 몫을 놓고 경쟁시키지 않는다(실측:
        # 라벨만 고치고 버리면 문항 수만 줄었다).
        limit = per_level * 2 if lv < requested else per_level
        if len(by_level[lv]) >= limit:
            continue
        seen.add(key)
        by_level[lv].append(p)
    return by_level


def _coverage_note(
    by_level: dict[int, list[Problem]],
    per_level: int,
    total_dropped: int,
    report: coverage.CoverageReport,
    call_failures: int = 0,
) -> str:
    """코드가 요청수 대비 실제수를 세어 노트를 만든다(LLM 자진신고 대체).

    이 노트는 진도 엔진의 입력이기도 하다 — "이 개념엔 L3가 없다"를 알아야
    L2 통과를 완료로 처리할 수 있고, 커버리지는 학습 완료 판정의 신뢰도다.
    """
    short = [
        f"L{lv} {len(by_level[lv])}/{per_level}"
        for lv in _LEVELS
        if len(by_level[lv]) < per_level
    ]
    parts: list[str] = [f"원문 커버리지 {report.percent}%"]
    if short:
        parts.append("목표 미달(재시도 후): " + ", ".join(short))
    else:
        parts.append(f"레벨별 목표({per_level}문항) 충족")
    if total_dropped:
        parts.append(f"검증 실패로 누적 {total_dropped}문항 폐기")
    if call_failures:
        # 부분 실패를 조용히 넘기지 않는다 — 문항이 적은 이유가 원문 탓인지
        # 호출 실패 탓인지 구분되어야 재생성 여부를 판단할 수 있다.
        parts.append(f"생성 호출 {call_failures}회 실패(타임아웃 등)")
    return ". ".join(parts) + "."
