"""PDF → 페이지 단위 청킹 + fallback skeleton.

청킹: 페이지 단위로 저장 (RAG 검색의 기본 단위).
Skeleton fallback: Solar 실패 시 챕터(5페이지) 단위로 개념 묶음.
  - 개념 1개 = 연속된 여러 페이지를 다루는 학습 단위
  - 페이지 1개 = 개념 1개가 되지 않도록 한다.
"""
from __future__ import annotations

import math
import uuid
from pathlib import Path

from pypdf import PdfReader

from app.features.materials.schemas import ConceptEntry, DocumentSkeleton, TocEntry

PAGES_PER_CONCEPT = 5   # fallback: 몇 페이지를 하나의 개념으로 묶을지
EXTERNAL_PREREQUISITES = [
    "linear_algebra_basics",
    "calculus_basics",
    "probability_basics",
]


def extract_pages(pdf_path: Path) -> list[tuple[int, str]]:
    reader = PdfReader(str(pdf_path))
    pages: list[tuple[int, str]] = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        pages.append((i, text or f"(page {i}: no extractable text)"))
    return pages


def _concept_title(idx: int, chapter_pages: list[tuple[int, str]]) -> str:
    """챕터 내 첫 번째 의미 있는 텍스트에서 제목 후보 추출."""
    for _, text in chapter_pages:
        if not text.startswith("(page "):
            first_line = text.split("\n")[0].strip()
            if len(first_line) >= 4:
                return f"단원 {idx}: {first_line[:60]}"
    return f"단원 {idx}"


def build_skeleton(
    document_id: uuid.UUID,
    pages: list[tuple[int, str]],
    chunk_ids: list[str],
) -> DocumentSkeleton:
    """
    Solar skeleton 실패 시 사용하는 규칙 기반 fallback.
    PAGES_PER_CONCEPT 페이지를 하나의 개념(concept)으로 묶어
    의미 단위에 가깝게 만든다.
    """
    page_count = len(pages)
    concept_count = max(1, math.ceil(page_count / PAGES_PER_CONCEPT))

    toc: list[TocEntry] = []
    concepts: list[ConceptEntry] = []

    for idx in range(1, concept_count + 1):
        start_idx = (idx - 1) * PAGES_PER_CONCEPT
        end_idx = min(idx * PAGES_PER_CONCEPT, page_count)

        concept_pages = pages[start_idx:end_idx]
        page_nums = [p[0] for p in concept_pages]

        toc.append(
            TocEntry(
                id=f"chapter_{idx}",
                title=f"Chapter {idx}",
                start_page=page_nums[0],
                end_page=page_nums[-1],
            )
        )

        # prior_concept_ids: 직전 개념에 의존 (순차 의존 가정)
        prior = [f"c{idx - 1}"] if idx > 1 else []

        concepts.append(
            ConceptEntry(
                id=f"c{idx}",
                title=_concept_title(idx, concept_pages),
                page_numbers=page_nums,
                chunk_ids=[],
                prior_concept_ids=prior,
            )
        )

    return DocumentSkeleton(
        document_id=document_id,
        page_count=page_count,
        toc=toc,
        concepts=concepts,
        external_prerequisites=EXTERNAL_PREREQUISITES.copy(),
    )
