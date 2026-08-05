"""1단계 — Upstage Document Parse. PDF/이미지 → 요소 배열.

판정은 하지 않는다. 순수 호출 + 형태 정규화만.

Document Parse가 붙이는 category(heading1 / header / paragraph …)를
**챕터 경계 판정에 쓰지 않는다.** 실측(2026-08-02): 같은 성격의 챕터 제목이
하나는 header, 하나는 heading1로 분류됐다. 경계는 7단계 목차 분류가 정한다.
여기서 category는 조각 경계 힌트와 노이즈 필터로만 쓴다.

Solar 1회.
"""
from __future__ import annotations

import logging

from app.core.llm.solar import solar_client
from app.features.parsing.schemas import Element

_log = logging.getLogger("uvicorn.error")

# 확장자 → (source_format, MIME). Document Parse가 받는 형식들.
_FORMATS: dict[str, tuple[str, str]] = {
    "pdf": ("pdf", "application/pdf"),
    "png": ("image", "image/png"),
    "jpg": ("image", "image/jpeg"),
    "jpeg": ("image", "image/jpeg"),
    "tiff": ("image", "image/tiff"),
    "bmp": ("image", "image/bmp"),
    "heic": ("image", "image/heic"),
}


def detect_format(filename: str) -> tuple[str, str]:
    """파일명 → (source_format, MIME). 모르는 확장자는 PDF로 시도한다."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _FORMATS.get(ext, ("pdf", "application/pdf"))


async def parse(file_bytes: bytes, filename: str) -> tuple[str, list[Element]]:
    """파일 → (마크다운, 요소 배열).

    요소 배열이 파이프라인의 1순위 입력이다. 마크다운은 보존·디버깅용.
    """
    _, mime = detect_format(filename)
    markdown, elements = await solar_client.parse_document(
        file_bytes, filename, content_type=mime
    )
    if not elements:
        raise ValueError(f"Document Parse가 요소를 반환하지 않았습니다: {filename}")

    _log.info("Document Parse 완료: %s — 요소 %d개", filename, len(elements))
    return markdown, elements
