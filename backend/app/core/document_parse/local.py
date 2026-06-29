"""pypdf 기반 로컬 PDF 파서 (Upstage Parse 실패·키 없음 fallback)."""
from __future__ import annotations

from pathlib import Path

from app.core.document_parse.base import DocumentParseResult, DocumentParser
from app.features.materials.parser import extract_pages


class LocalDocumentParser(DocumentParser):
    async def parse_pdf(self, pdf_path: Path) -> DocumentParseResult:
        pages = extract_pages(pdf_path)
        return DocumentParseResult(
            pages=pages,
            page_count=len(pages),
            engine="pypdf",
            note="pypdf 페이지 텍스트 추출",
        )
