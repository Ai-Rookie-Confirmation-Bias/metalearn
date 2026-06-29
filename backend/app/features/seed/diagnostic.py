"""진단 문제 생성 — Solar LLM 또는 rule-based fallback."""
from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass

from app.core.config import settings
from app.core.groundedness import verify_generated_content
from app.core.llm.base import LLMClient
from app.core.llm.factory import get_llm_client
from app.features.seed.concept_sources import ConceptSource

logger = logging.getLogger(__name__)

GenerationMode = str  # "llm" | "fallback"
_MAX_GROUNDEDNESS_RETRIES = 2


@dataclass
class DiagnosticGenerationResult:
    questions: list[dict]
    generation_mode: GenerationMode
    generation_note: str | None = None


def _rule_based_question(source: ConceptSource, all_previews: list[str]) -> dict:
    preview = source.text[:120].replace("\n", " ").strip()
    if len(preview) < 20:
        preview = f"페이지 {source.page_numbers[0]}의 핵심 내용"

    pool = [p for p in all_previews if p != preview]
    random.shuffle(pool)
    wrongs = pool[:3]
    while len(wrongs) < 3:
        wrongs.append(f"오답 후보 {len(wrongs) + 1}")

    options = [preview, *wrongs[:3]]
    random.shuffle(options)

    return {
        "concept_id": source.concept_id,
        "question_text": (
            f"[{source.concept_id}] 다음 중 해당 개념 내용과 가장 일치하는 설명은?"
        ),
        "options": options,
        "correct_index": options.index(preview),
        "source_chunk_id": source.chunk_ids[0] if source.chunk_ids else None,
    }


def _prior_context(
    source: ConceptSource,
    sources: dict[str, ConceptSource],
    concepts_in_range: list[str],
) -> str:
    parts: list[str] = []

    if source.prior_concept_ids:
        for pid in source.prior_concept_ids:
            prior = sources.get(pid)
            if prior:
                parts.append(f"[{pid}]\n{prior.text[:800]}")

    idx = concepts_in_range.index(source.concept_id) if source.concept_id in concepts_in_range else -1
    if idx > 0:
        prev_id = concepts_in_range[idx - 1]
        if prev_id not in source.prior_concept_ids:
            prior = sources.get(prev_id)
            if prior:
                parts.append(f"[직전 {prev_id}]\n{prior.text[:800]}")

    return "\n\n".join(parts)


def _build_llm_prompt(
    concepts_in_range: list[str],
    sources: dict[str, ConceptSource],
) -> str:
    blocks: list[str] = []
    for concept_id in concepts_in_range:
        source = sources.get(concept_id)
        if source is None:
            continue
        prior = _prior_context(source, sources, concepts_in_range)
        blocks.append(
            json.dumps(
                {
                    "concept_id": concept_id,
                    "page_numbers": source.page_numbers,
                    "source_text": source.text[:2500],
                    "immediate_prior_context": prior or None,
                },
                ensure_ascii=False,
            )
        )

    return f"""당신은 학습 플랫폼 진단 출제자입니다.

규칙:
1. concept마다 4지선다 1문항 (한국어).
2. 정답·오답은 source_text에서만 — 외부 지식·할루시네이션 금지.
3. immediate_prior_context가 있으면 그 맥락을 이해하는지 검사.
4. options 4개, correct_index 0~3.
5. question_text는 학습자에게 자연스러운 질문 형태 (원문 120자를 그대로 복붙하지 말 것).

concepts:
{chr(10).join(blocks)}

JSON만:
{{"questions": [{{"concept_id": "...", "question_text": "...", "options": ["...", "...", "...", "..."], "correct_index": 0}}]}}
"""


def _build_single_llm_prompt(
    concept_id: str,
    source: ConceptSource,
    sources: dict[str, ConceptSource],
    concepts_in_range: list[str],
) -> str:
    prior = _prior_context(source, sources, concepts_in_range)
    block = json.dumps(
        {
            "concept_id": concept_id,
            "page_numbers": source.page_numbers,
            "source_text": source.text[:2500],
            "immediate_prior_context": prior or None,
        },
        ensure_ascii=False,
    )
    return f"""당신은 학습 플랫폼 진단 출제자입니다.

규칙:
1. 아래 concept 1개에 대해 4지선다 1문항 (한국어).
2. 정답·오답은 source_text에서만 — 외부 지식·할루시네이션 금지.
3. options 4개, correct_index 0~3.

concept:
{block}

JSON만:
{{"questions": [{{"concept_id": "{concept_id}", "question_text": "...", "options": ["...", "...", "...", "..."], "correct_index": 0}}]}}
"""


def _parse_llm_questions(raw: str, sources: dict[str, ConceptSource]) -> list[dict]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    data = json.loads(text)
    items = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("invalid questions")

    specs: list[dict] = []
    for item in items:
        concept_id = item.get("concept_id")
        source = sources.get(concept_id)
        if source is None:
            continue
        options = item.get("options")
        correct_index = item.get("correct_index")
        question_text = item.get("question_text")
        if (
            not isinstance(options, list)
            or len(options) != 4
            or not isinstance(correct_index, int)
            or not (0 <= correct_index < 4)
            or not isinstance(question_text, str)
        ):
            continue
        specs.append(
            {
                "concept_id": concept_id,
                "question_text": question_text.strip(),
                "options": [str(o) for o in options],
                "correct_index": correct_index,
                "source_chunk_id": source.chunk_ids[0] if source.chunk_ids else None,
            }
        )
    return specs


def _question_content(spec: dict) -> str:
    return spec["question_text"] + "\n" + "\n".join(spec["options"])


async def _verify_question(spec: dict, source: ConceptSource) -> bool:
    result = await verify_generated_content(_question_content(spec), [source])
    return result.is_grounded


async def _generate_verified_question(
    llm: LLMClient,
    concept_id: str,
    source: ConceptSource,
    sources: dict[str, ConceptSource],
    concepts_in_range: list[str],
    all_previews: list[str],
) -> dict:
    for attempt in range(_MAX_GROUNDEDNESS_RETRIES + 1):
        try:
            prompt = _build_single_llm_prompt(
                concept_id, source, sources, concepts_in_range
            )
            raw = await llm.generate(prompt, json_mode=True)
            specs = _parse_llm_questions(raw, sources)
            spec = next((s for s in specs if s["concept_id"] == concept_id), None)
            if spec and await _verify_question(spec, source):
                return spec
            logger.warning(
                "진단 문제 groundedness 실패 (%s, attempt %d)",
                concept_id,
                attempt + 1,
            )
        except Exception:
            logger.exception("진단 문제 재생성 실패: %s", concept_id)

    return _rule_based_question(source, all_previews)


async def _ensure_grounded_specs(
    specs: list[dict],
    sources: dict[str, ConceptSource],
    concepts_in_range: list[str],
    all_previews: list[str],
    llm: LLMClient,
) -> list[dict]:
    verified: list[dict] = []
    for spec in specs:
        concept_id = spec["concept_id"]
        source = sources.get(concept_id)
        if source is None:
            continue
        if await _verify_question(spec, source):
            verified.append(spec)
            continue
        logger.warning("진단 문제 groundedness 실패, 재생성: %s", concept_id)
        verified.append(
            await _generate_verified_question(
                llm,
                concept_id,
                source,
                sources,
                concepts_in_range,
                all_previews,
            )
        )
    return verified


async def build_diagnostic_questions(
    concepts_in_range: list[str],
    sources: dict[str, ConceptSource],
) -> DiagnosticGenerationResult:
    all_previews = [s.text[:80].replace("\n", " ") for s in sources.values() if s.text.strip()]

    fallback_specs = [
        _rule_based_question(sources[cid], all_previews)
        for cid in concepts_in_range
        if cid in sources
    ]

    if settings.llm_provider == "mock":
        return DiagnosticGenerationResult(
            questions=fallback_specs,
            generation_mode="fallback",
            generation_note="API 키 없음 — 규칙 기반 문제",
        )

    llm = get_llm_client()
    prompt = _build_llm_prompt(concepts_in_range, sources)
    try:
        raw = await llm.generate(prompt, json_mode=True)
        specs = _parse_llm_questions(raw, sources)
        if specs:
            specs = await _ensure_grounded_specs(
                specs, sources, concepts_in_range, all_previews, llm
            )
            covered = {s["concept_id"] for s in specs}
            for cid in concepts_in_range:
                if cid not in covered and cid in sources:
                    specs.append(
                        await _generate_verified_question(
                            llm,
                            cid,
                            sources[cid],
                            sources,
                            concepts_in_range,
                            all_previews,
                        )
                    )
            partial = len(covered) < len(concepts_in_range)
            return DiagnosticGenerationResult(
                questions=specs,
                generation_mode="llm",
                generation_note=f"{settings.llm_provider_label}로 생성 (groundedness 검증)"
                + (" (일부 규칙 보완)" if partial else ""),
            )
    except Exception as exc:
        logger.exception("LLM 진단 문제 생성 실패")
        label = settings.llm_provider_label
        note = f"{label} API 실패 — 규칙 기반 fallback"
        if "429" in str(exc):
            note = f"{label} 요청 한도 초과(429) — 규칙 기반 fallback"
        return DiagnosticGenerationResult(
            questions=fallback_specs,
            generation_mode="fallback",
            generation_note=note,
        )

    return DiagnosticGenerationResult(
        questions=fallback_specs,
        generation_mode="fallback",
        generation_note=f"{settings.llm_provider_label} 응답 파싱 실패 — 규칙 기반 fallback",
    )
