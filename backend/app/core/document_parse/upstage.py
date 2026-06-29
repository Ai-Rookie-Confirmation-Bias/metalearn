"""Upstage Document Parse API — PDF → 구조화 markdown/text."""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from pathlib import Path

import httpx

from app.core.config import settings
from app.core.document_parse.base import DocumentParseResult, DocumentParser
from app.core.document_parse.local import LocalDocumentParser
from app.features.materials.parser import extract_pages

logger = logging.getLogger(__name__)

_SYNC_MAX_PAGES = 100
_TIMEOUT = 180.0
_POLL_INTERVAL = 3.0
_MAX_POLL_ATTEMPTS = 120


def _pages_from_elements(elements: list[dict]) -> list[tuple[int, str]]:
    by_page: dict[int, list[str]] = defaultdict(list)
    for el in elements:
        if not isinstance(el, dict):
            continue
        page = int(el.get("page") or 1)
        content = el.get("content") or {}
        if not isinstance(content, dict):
            continue
        text = (content.get("markdown") or content.get("text") or "").strip()
        if text:
            by_page[page].append(text)

    if not by_page:
        return []

    return [
        (page_num, "\n\n".join(blocks))
        for page_num, blocks in sorted(by_page.items())
    ]


def _pages_from_response(data: dict) -> list[tuple[int, str]]:
    pages = _pages_from_elements(data.get("elements") or [])
    if pages:
        return pages

    content = data.get("content") or {}
    if not isinstance(content, dict):
        return []

    full = (content.get("markdown") or content.get("text") or "").strip()
    if not full:
        return []

    usage = data.get("usage") or {}
    page_count = int(usage.get("pages") or 1) if isinstance(usage, dict) else 1
    if page_count <= 1:
        return [(1, full)]

    # elements 없이 전체 markdown만 온 경우 — 페이지 수만큼 균등 분할
    chunk_size = max(1, len(full) // page_count)
    split: list[tuple[int, str]] = []
    for i in range(page_count):
        start = i * chunk_size
        end = len(full) if i == page_count - 1 else start + chunk_size
        part = full[start:end].strip()
        if part:
            split.append((i + 1, part))
    return split or [(1, full)]


def _page_count_from_response(data: dict, pages: list[tuple[int, str]]) -> int:
    usage = data.get("usage") or {}
    if isinstance(usage, dict) and usage.get("pages"):
        return int(usage["pages"])
    if pages:
        return max(p for p, _ in pages)
    return len(pages)


class UpstageDocumentParser(DocumentParser):
    def __init__(self) -> None:
        self._headers = {"Authorization": f"Bearer {settings.UPSTAGE_API_KEY}"}
        self._base = settings.SOLAR_BASE_URL
        self._fallback = LocalDocumentParser()

    async def parse_pdf(self, pdf_path: Path) -> DocumentParseResult:
        try:
            page_estimate = len(extract_pages(pdf_path))
        except Exception:
            page_estimate = 1

        try:
            if page_estimate > _SYNC_MAX_PAGES:
                return await self._parse_async(pdf_path, page_estimate)
            return await self._parse_sync(pdf_path)
        except TimeoutError:
            logger.exception("Upstage Document Parse async 시간 초과, pypdf fallback")
        except Exception:
            logger.exception("Upstage Document Parse 실패, pypdf fallback")

        result = await self._fallback.parse_pdf(pdf_path)
        return DocumentParseResult(
            pages=result.pages,
            page_count=result.page_count,
            engine="pypdf",
            note="Document Parse 실패 — pypdf fallback",
        )

    async def _parse_sync(self, pdf_path: Path) -> DocumentParseResult:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            with pdf_path.open("rb") as f:
                resp = await client.post(
                    f"{self._base}/document-digitization",
                    headers=self._headers,
                    files={"document": (pdf_path.name, f, "application/pdf")},
                    data={
                        "model": settings.UPSTAGE_PARSE_MODEL,
                        "output_formats": '["markdown", "text"]',
                        "ocr": "auto",
                    },
                )
            resp.raise_for_status()
            data = resp.json()

        pages = _pages_from_response(data)
        if not pages:
            raise ValueError("Document Parse 응답에 페이지 텍스트가 없습니다.")

        return DocumentParseResult(
            pages=pages,
            page_count=_page_count_from_response(data, pages),
            engine="upstage",
            note=f"Upstage Document Parse ({settings.UPSTAGE_PARSE_MODEL})",
        )

    async def _parse_async(self, pdf_path: Path, page_estimate: int) -> DocumentParseResult:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            with pdf_path.open("rb") as f:
                resp = await client.post(
                    f"{self._base}/document-digitization/async",
                    headers=self._headers,
                    files={"document": (pdf_path.name, f, "application/pdf")},
                    data={
                        "model": settings.UPSTAGE_PARSE_MODEL,
                        "output_formats": '["markdown", "text"]',
                    },
                )
            resp.raise_for_status()
            request_id = resp.json()["request_id"]

            for _ in range(_MAX_POLL_ATTEMPTS):
                status_resp = await client.get(
                    f"{self._base}/document-digitization/requests/{request_id}",
                    headers=self._headers,
                )
                status_resp.raise_for_status()
                status = status_resp.json()

                if status.get("status") == "completed":
                    all_pages: list[tuple[int, str]] = []
                    batches = sorted(status.get("batches") or [], key=lambda b: b.get("id", 0))
                    for batch in batches:
                        if batch.get("status") != "completed" or not batch.get("download_url"):
                            continue
                        batch_resp = await client.get(batch["download_url"])
                        batch_resp.raise_for_status()
                        batch_data = batch_resp.json()
                        batch_pages = _pages_from_response(batch_data)
                        for page_num, text in batch_pages:
                            all_pages.append((page_num, text))

                    if not all_pages:
                        raise ValueError("Document Parse async 결과가 비어 있습니다.")

                    all_pages.sort(key=lambda x: x[0])
                    return DocumentParseResult(
                        pages=all_pages,
                        page_count=status.get("total_pages") or len(all_pages),
                        engine="upstage",
                        note=f"Upstage Document Parse async ({page_estimate}p)",
                    )

                if status.get("status") == "failed":
                    raise RuntimeError(status.get("failure_message") or "Document Parse async 실패")

                await asyncio.sleep(_POLL_INTERVAL)

        raise TimeoutError("Document Parse async 폴링 시간 초과")
