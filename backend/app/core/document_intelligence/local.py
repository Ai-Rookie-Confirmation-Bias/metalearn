"""pypdf + 고정 규칙 skeleton (LLM 없음)."""
from __future__ import annotations

import uuid

from app.core.document_intelligence.base import DocumentIntelligence
from app.features.materials.parser import build_skeleton
from app.features.materials.schemas import DocumentSkeleton
from app.features.seed.schemas import (
    LearningRange,
    PrerequisiteAnalysis,
    PrerequisiteSuggestion,
)


class LocalDocumentIntelligence(DocumentIntelligence):
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
        chunk_ids = [page_to_chunk_id[p[0]] for p in pages]
        return build_skeleton(document_id, pages, chunk_ids), "local", "pypdf 페이지 규칙"

    async def analyze_prerequisites(
        self,
        skeleton: DocumentSkeleton,
        learning_range: LearningRange,
    ) -> PrerequisiteAnalysis:
        toc_by_id = {t.id: t for t in skeleton.toc}
        start = toc_by_id.get(learning_range.start)
        suggestions: list[PrerequisiteSuggestion] = []

        if start:
            for t in skeleton.toc:
                if t.end_page < start.start_page:
                    suggestions.append(
                        PrerequisiteSuggestion(
                            id=t.id,
                            label=t.title,
                            source="in_document",
                            reason="학습 시작 범위 이전 단원입니다.",
                            recommended=True,
                        )
                    )

        for ext_id in skeleton.external_prerequisites:
            suggestions.append(
                PrerequisiteSuggestion(
                    id=ext_id,
                    label=ext_id.replace("_", " "),
                    source="external",
                    reason="교재 밖에서 자주 요구되는 선행지식 후보입니다.",
                    recommended=False,
                )
            )

        return PrerequisiteAnalysis(
            suggestions=suggestions,
            concepts_needing_prereq=[],
            summary="규칙 기반 선행지식 목록입니다.",
            generation_mode="local",
            generation_note="API 키 없음",
        )

    async def enrich_curriculum_units(
        self,
        units: list[dict],
        skeleton: DocumentSkeleton,
        learning_goal: str | None,
        weaknesses: list[str],
    ) -> list[dict]:
        return units
