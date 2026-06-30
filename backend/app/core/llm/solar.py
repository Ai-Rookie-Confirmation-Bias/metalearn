"""Upstage Solar 통신 구현체 (OpenAI 호환 API). MVP 메인 생성 엔진.

- generate / embed: LLMClient 계약 구현 (온/오프라인 패리티 대상)
- parse_document / generate_json: Solar 전용 확장 (클라우드 전용, Ingestion용)
"""
import json
from typing import Any

import httpx

from app.core.config import settings
from app.core.llm.base import LLMClient

# 외부 API 타임아웃(초). solar-pro3는 추론형이라 단일 생성이 길어질 수 있어 넉넉히.
# 문서 파싱은 페이지가 많으면 더 길어질 수 있음.
_GEN_TIMEOUT = 120.0
_BATCH_TIMEOUT = 240.0
_PARSE_TIMEOUT = 180.0


class SolarClient(LLMClient):
    def __init__(self) -> None:
        self._headers = {"Authorization": f"Bearer {settings.UPSTAGE_API_KEY}"}
        self._base = settings.SOLAR_BASE_URL

    async def generate(self, prompt: str, **kwargs: object) -> str:
        async with httpx.AsyncClient(
            base_url=self._base, headers=self._headers, timeout=_GEN_TIMEOUT
        ) as c:
            resp = await c.post(
                "/chat/completions",
                json={
                    "model": settings.SOLAR_CHAT_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(
            base_url=self._base, headers=self._headers, timeout=_GEN_TIMEOUT
        ) as c:
            resp = await c.post(
                "/embeddings",
                json={"model": settings.SOLAR_EMBED_MODEL, "input": text},
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]

    async def parse_document(self, file_bytes: bytes, filename: str) -> str:
        """Solar Document Parse: PDF 바이트 → 마크다운 문자열.

        Upstage Document Digitization API. 응답의 content.markdown을 사용하되
        스키마 변동에 대비해 markdown→text→html 순으로 폴백한다.
        """
        async with httpx.AsyncClient(
            base_url=self._base, headers=self._headers, timeout=_PARSE_TIMEOUT
        ) as c:
            resp = await c.post(
                "/document-digitization",
                files={"document": (filename, file_bytes, "application/pdf")},
                data={
                    "model": settings.DOCUMENT_PARSE_MODEL,
                    "output_formats": '["markdown"]',
                    "ocr": "auto",
                },
            )
            resp.raise_for_status()
            content = resp.json().get("content", {})
            return content.get("markdown") or content.get("text") or content.get("html") or ""

    async def generate_json(
        self, prompt: str, *, system: str | None = None, timeout: float = _GEN_TIMEOUT
    ) -> dict[str, Any]:
        """JSON 객체를 강제로 받아 dict로 파싱.

        response_format=json_object로 비정형 텍스트/할루시네이션 혼입을 1차 차단하고,
        호출부(service)에서 Pydantic 스키마로 2차 검증한다.
        """
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(
            base_url=self._base, headers=self._headers, timeout=timeout
        ) as c:
            resp = await c.post(
                "/chat/completions",
                json={
                    "model": settings.SOLAR_CHAT_MODEL,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
        return json.loads(raw)


solar_client = SolarClient()
