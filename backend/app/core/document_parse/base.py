"""PDF 텍스트 추출 추상 인터페이스 — Upstage Document Parse / pypdf 교체 지점."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DocumentParseResult:
    pages: list[tuple[int, str]]
    page_count: int
    engine: str  # "upstage" | "pypdf"
    note: str | None = None


class DocumentParser(ABC):
    @abstractmethod
    async def parse_pdf(self, pdf_path: Path) -> DocumentParseResult:
        """PDF → 페이지별 텍스트(markdown 우선)."""
