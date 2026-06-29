"""커리큘럼 단원별 학습 콘텐츠 생성 — Solar가 PDF 원문을 보고 설명 마크다운을 만든다."""
from __future__ import annotations

import asyncio
import logging

from app.core.groundedness import verify_generated_content
from app.core.llm.base import LLMClient
from app.features.seed.concept_sources import ConceptSource
from app.features.seed.weakness_utils import weakness_id_set

logger = logging.getLogger(__name__)

_MAX_CONCURRENT = 3
_MAX_GROUNDEDNESS_RETRIES = 2
_SOURCE_CHAR_LIMIT = 4000

GOAL_INSTRUCTION = {
    "exam": "시험 출제 가능성이 높은 핵심 개념·용어·공식을 강조하세요. 암기 포인트를 명확히 표시하세요.",
    "concept_understanding": "개념의 '왜'와 '어떻게'를 중심으로 설명하세요. 비유와 직관적 예시를 적극 활용하세요.",
    "problem_solving": "실제 문제 풀이에 적용할 수 있는 원리와 절차를 중심으로 설명하세요.",
    "skim": "핵심 키워드와 한 줄 정의 위주로 간결하게 정리하세요.",
}


def _make_prompt(
    title: str,
    source_text: str,
    learning_goal: str | None,
    is_weakness: bool,
    prior_titles: list[str],
) -> str:
    goal_hint = GOAL_INSTRUCTION.get(learning_goal or "", "")
    weakness_hint = (
        "\n⚠️ 진단에서 이 개념을 틀렸습니다. 오개념이 생기기 쉬운 부분을 특별히 짚어주세요."
        if is_weakness
        else ""
    )
    prior_hint = (
        f"\n선행 개념: {', '.join(prior_titles)}" if prior_titles else ""
    )

    return f"""당신은 대학 수준 학습 콘텐츠 작성 전문가입니다.
아래 PDF 원문을 바탕으로 **한국어 학습 노트**를 마크다운으로 작성하세요.

규칙:
1. PDF 원문에 있는 내용만 사용 — 외부 지식·할루시네이션 금지.
2. 다음 섹션을 순서대로 작성:
   - ## 개념 정의 (1~3문장으로 명확히)
   - ## 핵심 포인트 (불릿 3~6개, 각 항목은 완전한 문장)
   - ## 비유 / 예시 (원문 기반, 없으면 생략)
   - ## 연결 개념 (이 개념을 이해하면 자연스럽게 연결되는 다음 개념, 없으면 생략)
3. 각 섹션은 짧고 명확하게 — 전체 500~800자 목표.
4. {goal_hint}{weakness_hint}{prior_hint}

단원 제목: {title}

PDF 원문:
{source_text[:_SOURCE_CHAR_LIMIT]}

마크다운만 출력 (JSON 아님):"""


async def generate_unit_content(
    unit: dict,
    source: ConceptSource | None,
    learning_goal: str | None,
    weaknesses: set[str],
    llm: LLMClient,
    prior_sources: list[ConceptSource],
) -> tuple[str | None, bool]:
    if source is None or not source.text.strip():
        return None, False

    prior_titles = [s.concept_id for s in prior_sources if s.text.strip()]
    prompt = _make_prompt(
        title=unit.get("title", unit["concept_id"]),
        source_text=source.text,
        learning_goal=learning_goal,
        is_weakness=unit["concept_id"] in weaknesses,
        prior_titles=prior_titles,
    )

    content: str | None = None
    try:
        for attempt in range(_MAX_GROUNDEDNESS_RETRIES + 1):
            raw = await llm.generate(prompt, json_mode=False)
            content = raw.strip() if raw else None
            if not content:
                continue

            result = await verify_generated_content(content, [source])
            if result.is_grounded:
                return content, True

            logger.warning(
                "unit content groundedness 실패 (%s, attempt %d): %s",
                unit.get("concept_id"),
                attempt + 1,
                result.reason,
            )

        return content, False
    except Exception:
        logger.exception("단원 콘텐츠 생성 실패: %s", unit.get("concept_id"))
        return None, False


async def generate_all_unit_contents(
    units: list[dict],
    sources: dict[str, ConceptSource],
    learning_goal: str | None,
    weaknesses: list,
    llm: LLMClient,
) -> list[dict]:
    if not units:
        return units

    weakness_set = weakness_id_set(weaknesses)
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

    async def _bounded(unit: dict) -> dict:
        concept_id = unit["concept_id"]
        source = sources.get(concept_id)

        prior: list[ConceptSource] = []
        if source:
            for pid in source.prior_concept_ids:
                ps = sources.get(pid)
                if ps:
                    prior.append(ps)

        async with semaphore:
            content, is_verified = await generate_unit_content(
                unit=unit,
                source=source,
                learning_goal=learning_goal,
                weaknesses=weakness_set,
                llm=llm,
                prior_sources=prior,
            )
        return {**unit, "content": content, "is_verified": is_verified}

    results = await asyncio.gather(*[_bounded(u) for u in units])
    return list(results)
