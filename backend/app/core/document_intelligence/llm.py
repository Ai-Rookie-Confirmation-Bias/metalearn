"""Solar chat API 기반 문서 지능 (Parse API 전 PoC).

Upstage Document Parse + IE로 교체 시 이 모듈의 프롬프트·스키마만 이식하면 됨.
"""
from __future__ import annotations

import json
import logging
import uuid

from app.core.config import settings
from app.core.document_intelligence.base import DocumentIntelligence
from app.core.document_intelligence.local import LocalDocumentIntelligence
from app.core.llm.base import LLMClient
from app.features.materials.parser import build_skeleton
from app.features.materials.schemas import ConceptEntry, DocumentSkeleton, TocEntry
from app.features.seed.schemas import (
    LearningRange,
    PrerequisiteAnalysis,
    PrerequisiteSuggestion,
)

logger = logging.getLogger(__name__)

MAX_PAGES_SINGLE_CALL = 80  # Solar Pro2 context 여유분


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("JSON object expected")
    return data


def _format_pages(pages: list[tuple[int, str]]) -> str:
    # 전체 텍스트 합계를 ~60 000자로 제한
    max_per_page = max(300, 60_000 // max(len(pages), 1))
    blocks = []
    for num, text in pages:
        blocks.append(f"=== PAGE {num} ===\n{text[:max_per_page]}")
    return "\n\n".join(blocks)


def _attach_chunk_ids(
    concepts: list[dict],
    page_to_chunk_id: dict[int, str],
) -> list[ConceptEntry]:
    result: list[ConceptEntry] = []
    for c in concepts:
        page_numbers = c.get("page_numbers") or []
        if isinstance(page_numbers, int):
            page_numbers = [page_numbers]
        chunk_ids = [page_to_chunk_id[p] for p in page_numbers if p in page_to_chunk_id]
        if not page_numbers:
            continue
        result.append(
            ConceptEntry(
                id=str(c["id"]),
                title=str(c.get("title") or c["id"]),
                page_numbers=[int(p) for p in page_numbers],
                chunk_ids=[str(cid) for cid in chunk_ids],
                prior_concept_ids=[str(x) for x in c.get("prior_concept_ids") or []],
            )
        )
    return result


class LLMDocumentIntelligence(DocumentIntelligence):
    def __init__(self, client: LLMClient) -> None:
        self._llm = client

    async def build_skeleton(
        self,
        document_id: uuid.UUID,
        pages: list[tuple[int, str]],
        page_to_chunk_id: dict[int, str],
    ) -> DocumentSkeleton:
        sk, _, _ = await self.build_skeleton_with_meta(document_id, pages, page_to_chunk_id)
        return sk

    async def build_skeleton_with_meta(
        self,
        document_id: uuid.UUID,
        pages: list[tuple[int, str]],
        page_to_chunk_id: dict[int, str],
    ) -> tuple[DocumentSkeleton, str, str | None]:
        if len(pages) > MAX_PAGES_SINGLE_CALL:
            logger.warning("페이지 %d > %d, local skeleton fallback", len(pages), MAX_PAGES_SINGLE_CALL)
            chunk_ids = [page_to_chunk_id[p[0]] for p in pages]
            sk = build_skeleton(document_id, pages, chunk_ids)
            return sk, "local", f"페이지 {len(pages)}장 — LLM 한도, 규칙 fallback"

        prompt = f"""당신은 교육용 PDF 구조 분석기입니다.
총 {len(pages)}페이지 문서에서 학생이 실제로 공부할 **핵심 개념 단위**를 추출하세요.

━━━ 핵심 규칙 ━━━
[concepts]
- 페이지 1개 ≠ 개념 1개. 관련 내용이 이어지는 여러 페이지를 하나의 개념으로 묶으세요.
- 전체 문서에서 5~15개의 의미 있는 학습 단위를 뽑으세요.
- title: 학생이 "이걸 공부했다"고 말할 수 있는 실제 주제명
  (예: "OSI 7계층 모델의 역할과 구조", "TCP와 UDP의 차이", "HCI 설계 원칙")
  "p.3: ..." 같은 페이지 참조 제목은 절대 사용 금지.
- page_numbers: 해당 개념이 설명된 모든 페이지 번호 목록
- prior_concept_ids: 이 개념을 이해하기 위해 먼저 알아야 할 같은 문서 내 concept id
  (실제 내용 의존관계 기준, 단순 순서 아님. 없으면 [])
- id: c1, c2, ... 순서대로

[toc]
- 문서의 실제 목차/챕터 (없으면 내용 기반으로 묶어 추론)
- id: chapter_1, chapter_2, ...

[external_prerequisites]
- 이 문서를 이해하기 위해 PDF 밖에서 필요한 선행 지식 slug
- 문서 내용에 근거한 것만 (예: linear_algebra_basics, probability_basics)

PDF에 없는 내용을 추가하지 마세요.

페이지 텍스트:
{_format_pages(pages)}

JSON만 출력:
{{
  "toc": [{{"id": "chapter_1", "title": "챕터 제목", "start_page": 1, "end_page": 8}}],
  "concepts": [
    {{"id": "c1", "title": "실제 학습 주제명", "page_numbers": [1, 2, 3], "prior_concept_ids": []}},
    {{"id": "c2", "title": "두 번째 주제명", "page_numbers": [4, 5], "prior_concept_ids": ["c1"]}}
  ],
  "external_prerequisites": []
}}
"""
        try:
            raw = await self._llm.generate(prompt, json_mode=True)
            data = _parse_json(raw)
            toc = [TocEntry.model_validate(t) for t in data.get("toc") or []]
            concepts = _attach_chunk_ids(data.get("concepts") or [], page_to_chunk_id)
            if not toc or not concepts:
                raise ValueError("empty toc or concepts")

            return (
                DocumentSkeleton(
                    document_id=document_id,
                    page_count=len(pages),
                    toc=toc,
                    concepts=concepts,
                    external_prerequisites=[str(x) for x in data.get("external_prerequisites") or []],
                ),
                "llm",
                f"{settings.llm_provider_label}로 목차·개념 분석",
            )
        except Exception:
            logger.exception("LLM skeleton 실패, local fallback")
            chunk_ids = [page_to_chunk_id[p[0]] for p in pages]
            sk = build_skeleton(document_id, pages, chunk_ids)
            return sk, "local", f"{settings.llm_provider_label} skeleton 실패 — 페이지 규칙 fallback"

    async def analyze_prerequisites(
        self,
        skeleton: DocumentSkeleton,
        learning_range: LearningRange,
    ) -> PrerequisiteAnalysis:
        prompt = f"""학습 범위와 skeleton을 보고 선행지식을 분석하세요.

학습 범위: {learning_range.model_dump_json()}

skeleton:
{json.dumps(skeleton.model_dump(mode="json"), ensure_ascii=False)[:12000]}

규칙:
1. PDF 안(in_document): 학습 시작 전 알면 좋은 chapter/concept id
2. PDF 밖(external): slug id + 한국어 label
3. recommended=true는 진단 전 꼭 확인하면 좋은 항목
4. concepts_needing_prereq: 학습 범위 내 concept 중 선행 확인이 필요한 id
5. PDF에 근거 없는 항목 추가 금지

JSON만:
{{"suggestions": [{{"id": "...", "label": "...", "source": "in_document|external", "reason": "...", "recommended": true}}],
  "concepts_needing_prereq": ["c3"],
  "summary": "한 줄 요약"}}
"""
        try:
            raw = await self._llm.generate(prompt, json_mode=True)
            data = _parse_json(raw)
            suggestions = [PrerequisiteSuggestion.model_validate(s) for s in data.get("suggestions") or []]
            return PrerequisiteAnalysis(
                suggestions=suggestions,
                concepts_needing_prereq=[str(x) for x in data.get("concepts_needing_prereq") or []],
                summary=str(data.get("summary") or ""),
                generation_mode="llm",
                generation_note=f"{settings.llm_provider_label} 선행지식 분석",
            )
        except Exception:
            logger.exception("LLM prerequisite analysis 실패, local fallback")
            result = await local_intelligence.analyze_prerequisites(skeleton, learning_range)
            return result.model_copy(
                update={"generation_note": f"{settings.llm_provider_label} 실패 — 규칙 기반 목록"}
            )

    async def enrich_curriculum_units(
        self,
        units: list[dict],
        skeleton: DocumentSkeleton,
        learning_goal: str | None,
        weaknesses: list[str],
    ) -> list[dict]:
        if not units:
            return units

        prompt = f"""커리큘럼 단원 목록에 학습 안내를 추가하세요.

learning_goal: {learning_goal or "없음"}
weaknesses: {weaknesses}
units: {json.dumps(units, ensure_ascii=False)[:10000]}

각 unit에 summary(1문장), focus(이 단원에서 할 일 1문장) 추가. PDF 밖 사실 금지.

JSON만: {{"units": [{{ ...기존 필드..., "summary": "...", "focus": "..."}}]}}
"""
        try:
            raw = await self._llm.generate(prompt, json_mode=True)
            data = _parse_json(raw)
            enriched = data.get("units")
            if not isinstance(enriched, list) or len(enriched) != len(units):
                return units
            merged = []
            for orig, new in zip(units, enriched, strict=True):
                merged.append({**orig, **{k: new[k] for k in ("summary", "focus") if k in new}})
            return merged
        except Exception:
            logger.exception("LLM curriculum enrich 실패")
            return units


local_intelligence = LocalDocumentIntelligence()
