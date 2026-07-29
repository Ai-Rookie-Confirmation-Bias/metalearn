"""[3.Service] 문제 생성 에이전트 오케스트레이션.

개념별로 프롬프트를 만들어 Solar에 JSON 생성을 요청하고,
반환 JSON을 안전하게 파싱·검증해 유효 문항만 결과에 싣는다.
부족·폐기분은 사유와 함께 재요청하는 자기수정 루프를 돈다(단발 호출 X).
개수 충족/미달은 LLM 자진신고가 아니라 코드가 세어 coverage_note를 만든다.
(DB 적재는 검증 에이전트 통과분만 — v1은 생성·검증(curl)까지.)
"""
import asyncio
import json
import logging

from pydantic import ValidationError

from app.core.llm.base import LLMClient
from app.core.llm.solar import solar_client
from app.features.problems.grounding import evidence_in_source, normalize
from app.features.problems.prompts import build_generation_prompt
from app.features.problems.quality import (
    answer_leaked_in_title,
    is_free_response_style,
    strip_option_label,
)
from app.features.problems import solve_check
from app.features.problems.schemas import (
    ConceptInput,
    ConceptProblems,
    GenerateProblemsRequest,
    GenerateProblemsResponse,
    Problem,
)

logger = logging.getLogger(__name__)

# 최초 1회 + 재시도 횟수. 부족/폐기분을 사유와 함께 재요청한다.
MAX_RETRIES = 2
_LEVELS: tuple[int, ...] = (1, 2, 3)


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


class ProblemGeneratorService:
    def __init__(self, llm: LLMClient | None = None) -> None:
        # 기본은 팀 스택 Solar. LLMClient 계약 뒤라 교체 가능.
        self.llm = llm or solar_client

    async def generate(
        self, req: GenerateProblemsRequest
    ) -> GenerateProblemsResponse:
        # 개념 간 의존이 없으므로 병렬 생성(레포 선례 30f9977의 gather 패턴).
        results = await asyncio.gather(
            *(
                self._generate_for_concept(req.subject, concept, req.per_level)
                for concept in req.concepts
            )
        )
        return GenerateProblemsResponse(subject=req.subject, results=list(results))

    async def _generate_for_concept(
        self, subject: str, concept: ConceptInput, per_level: int
    ) -> ConceptProblems:
        """레벨별 목표 수를 채울 때까지 부족분을 사유와 함께 재요청한다.

        단발 호출이 아니라 자기수정 루프(최대 MAX_RETRIES회 추가 시도):
        매 시도마다 검증 통과분을 누적하고, 부족한 레벨·직전 폐기 사유를
        다음 프롬프트에 피드백으로 넣는다. 목표를 채우면 즉시 탈출.
        """
        by_level: dict[int, list[Problem]] = {lv: [] for lv in _LEVELS}
        seen: set[str] = set()  # 중복 문항 차단(정규화 질문 기준)
        total_dropped = 0
        feedback: str | None = None

        for attempt in range(MAX_RETRIES + 1):
            deficit = {lv: per_level - len(by_level[lv]) for lv in _LEVELS}
            if all(n <= 0 for n in deficit.values()):
                break

            prompt = build_generation_prompt(
                subject, concept, per_level, feedback=feedback
            )
            try:
                raw = await self.llm.generate(
                    prompt,
                    response_format={"type": "json_object"},
                    temperature=0.4,
                )
                data = _extract_json_object(raw)
            except json.JSONDecodeError:
                logger.warning(
                    "concept %s attempt %d: JSON 파싱 실패",
                    concept.concept_id,
                    attempt,
                )
                feedback = (
                    "직전 응답이 JSON으로 파싱되지 않았다. "
                    "코드펜스·설명 없이 JSON 객체 하나만 출력하라."
                )
                continue

            fresh, dropped, reasons = self._validate_problems(
                data.get("problems", []), concept
            )
            # [게이트4] 검수 LLM이 직접 풀어 정답 비유일·풀이불가를 걸러낸다.
            # 기계 게이트를 통과한 것만 넘겨 검수 호출을 아낀다.
            if fresh:
                fresh, solve_reasons = await solve_check.verify_problems(
                    self.llm, fresh, concept.source_text
                )
                dropped += len(solve_reasons)
                reasons.extend(solve_reasons)
            total_dropped += dropped
            for p in fresh:
                lv = int(p.level)
                key = normalize(p.question)
                if key in seen or len(by_level[lv]) >= per_level:
                    continue  # 중복이거나 이미 목표를 채운 레벨은 버린다
                seen.add(key)
                by_level[lv].append(p)

            deficit = {lv: per_level - len(by_level[lv]) for lv in _LEVELS}
            if all(n <= 0 for n in deficit.values()):
                break
            feedback = _build_feedback(deficit, reasons)

        problems = [p for lv in _LEVELS for p in by_level[lv]]
        return ConceptProblems(
            concept_id=concept.concept_id,
            title=concept.title,
            chapter_id=concept.chapter_id,
            chapter_title=concept.chapter_title,
            problems=problems,
            coverage_note=_coverage_note(by_level, per_level, total_dropped),
        )

    @staticmethod
    def _validate_problems(
        rawitems: object, concept: ConceptInput
    ) -> tuple[list[Problem], int, list[str]]:
        """개별 문항을 검증 — 한 문항이 깨져도 나머지는 살린다.

        게이트: ① Pydantic(정답=보기 일치 등) ② 지문 형식(객관식다움)
        ③ source_evidence 원문 실재. 폐기 사유는 재시도 프롬프트의 피드백이 된다.
        """
        problems: list[Problem] = []
        reasons: list[str] = []
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
            problems.append(p)
        return problems, len(reasons), reasons


def _normalize_options(item: object) -> object:
    """보기·정답 앞에 LLM이 붙인 자체 라벨("A. ", "1) ")을 제거한다.

    라벨이 남으면 화면에서 "A) A. FIFO"로 겹쳐 보이고, answer와 options의
    글자 일치가 깨져 멀쩡한 문항이 검증에서 폐기된다.
    """
    if not isinstance(item, dict):
        return item
    out = dict(item)
    if isinstance(out.get("options"), list):
        out["options"] = [strip_option_label(str(o)) for o in out["options"]]
    if isinstance(out.get("answer"), str):
        out["answer"] = strip_option_label(out["answer"])
    return out


def _build_feedback(deficit: dict[int, int], reasons: list[str]) -> str:
    """부족 레벨과 폐기 사유를 다음 시도 프롬프트용 지시로 정리."""
    short = [f"level {lv} {n}문항" for lv, n in deficit.items() if n > 0]
    lines: list[str] = []
    if short:
        lines.append("아직 부족한 레벨을 이만큼 더 만들어라: " + ", ".join(short) + ".")
    if reasons:
        lines.append("직전 폐기 사유: " + " / ".join(sorted(set(reasons))) + ".")
    lines.append(
        "이미 만든 문항과 중복되지 않게, 원문 근거를 그대로 인용해 출제하라."
    )
    return "\n".join(lines)


def _coverage_note(
    by_level: dict[int, list[Problem]], per_level: int, total_dropped: int
) -> str:
    """코드가 요청수 대비 실제수를 세어 노트를 만든다(LLM 자진신고 대체)."""
    short = [
        f"L{lv} {len(by_level[lv])}/{per_level}"
        for lv in _LEVELS
        if len(by_level[lv]) < per_level
    ]
    parts: list[str] = []
    if short:
        parts.append("목표 미달(재시도 후): " + ", ".join(short))
    if total_dropped:
        parts.append(
            f"검증 실패로 누적 {total_dropped}문항 폐기(원문 근거 불일치/정답 형식 오류)"
        )
    if not parts:
        return f"레벨별 목표({per_level}문항) 충족."
    return ". ".join(parts) + "."
