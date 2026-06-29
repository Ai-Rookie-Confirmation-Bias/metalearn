"""문서 지능 레이어 추상 인터페이스 — Solar/Upstage Parse 교체 지점."""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.features.materials.schemas import DocumentSkeleton
from app.features.seed.schemas import LearningRange, PrerequisiteAnalysis


class DocumentIntelligence(ABC):
    @abstractmethod
    async def build_skeleton(
        self,
        document_id: uuid.UUID,
        pages: list[tuple[int, str]],
        page_to_chunk_id: dict[int, str],
    ) -> DocumentSkeleton:
        """PDF 페이지 텍스트 → 목차·개념 skeleton."""

    async def build_skeleton_with_meta(
        self,
        document_id: uuid.UUID,
        pages: list[tuple[int, str]],
        page_to_chunk_id: dict[int, str],
    ) -> tuple[DocumentSkeleton, str, str | None]:
        """skeleton + parse_mode + parse_note. 기본 구현은 build_skeleton 래핑."""
        sk = await self.build_skeleton(document_id, pages, page_to_chunk_id)
        return sk, "local", None

    @abstractmethod
    async def analyze_prerequisites(
        self,
        skeleton: DocumentSkeleton,
        learning_range: LearningRange,
    ) -> PrerequisiteAnalysis:
        """학습 범위 기준 선행지식 후보·권장 탐색."""

    @abstractmethod
    async def enrich_curriculum_units(
        self,
        units: list[dict],
        skeleton: DocumentSkeleton,
        learning_goal: str | None,
        weaknesses: list[str],
    ) -> list[dict]:
        """커리큘럼 단원에 summary·focus 추가."""
