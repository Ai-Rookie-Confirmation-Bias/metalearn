"""Upstage Solar 통신 구현체 (OpenAI 호환 API). MVP 메인 생성 엔진.

- generate / embed: LLMClient 계약 구현 (온/오프라인 패리티 대상)
- parse_document / generate_json: Solar 전용 확장 (클라우드 전용, Ingestion용)
"""
import asyncio
import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.core.llm.base import LLMClient

# uvicorn 핸들러를 상속해 docker logs에서 바로 보이도록 (진행 관찰용)
_log = logging.getLogger("uvicorn.error")

# 외부 API 타임아웃(초). solar-pro3는 추론형이라 단일 생성이 길어질 수 있어 넉넉히.
# 문서 파싱은 페이지가 많으면 더 길어질 수 있음.
_GEN_TIMEOUT = 120.0
_BATCH_TIMEOUT = 240.0
_PARSE_TIMEOUT = 180.0

# 일시 오류 백오프 재시도. 섹션 분할 추출로 호출량이 늘어(특히 개념당 embed
# 연속 호출) 429 rate limit과 게이트웨이 5xx를 흡수할 장치가 필요 (ISSUE-008).
_TRANSIENT_RETRIES = 5
_TRANSIENT_STATUS = {429, 500, 502, 503, 504}


async def _post_retrying(client: httpx.AsyncClient, url: str, **kwargs: Any) -> httpx.Response:
    """POST 후 일시 오류(429/5xx/타임아웃)면 백오프 대기 후 재시도.

    429는 Retry-After 헤더를 존중하고, 그 외에는 지수 백오프.
    """
    for attempt in range(_TRANSIENT_RETRIES + 1):
        try:
            resp = await client.post(url, **kwargs)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            if attempt == _TRANSIENT_RETRIES:
                raise
            delay = 2.0 * (2**attempt)
            _log.warning("Upstage %s %s — %.0fs 후 재시도(%d/%d)", url, type(exc).__name__, delay, attempt + 1, _TRANSIENT_RETRIES)
            await asyncio.sleep(delay)
            continue
        if resp.status_code not in _TRANSIENT_STATUS or attempt == _TRANSIENT_RETRIES:
            resp.raise_for_status()
            return resp
        retry_after = resp.headers.get("retry-after")
        delay = (
            float(retry_after)
            if retry_after and retry_after.replace(".", "", 1).isdigit()
            else 2.0 * (2**attempt)
        )
        _log.warning("Upstage %s HTTP %d — %.0fs 후 재시도(%d/%d)", url, resp.status_code, delay, attempt + 1, _TRANSIENT_RETRIES)
        await asyncio.sleep(delay)
    raise AssertionError("unreachable")


class SolarClient(LLMClient):
    def __init__(self) -> None:
        self._headers = {"Authorization": f"Bearer {settings.UPSTAGE_API_KEY}"}
        self._base = settings.SOLAR_BASE_URL

    async def generate(self, prompt: str, **kwargs: object) -> str:
        async with httpx.AsyncClient(
            base_url=self._base, headers=self._headers, timeout=_GEN_TIMEOUT
        ) as c:
            resp = await _post_retrying(
                c,
                "/chat/completions",
                json={
                    "model": settings.SOLAR_CHAT_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            return resp.json()["choices"][0]["message"]["content"]

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(
            base_url=self._base, headers=self._headers, timeout=_GEN_TIMEOUT
        ) as c:
            resp = await _post_retrying(
                c,
                "/embeddings",
                json={"model": settings.SOLAR_EMBED_MODEL, "input": text},
            )
            return resp.json()["data"][0]["embedding"]

    async def parse_document(
        self, file_bytes: bytes, filename: str
    ) -> tuple[str, list[dict[str, Any]]]:
        """Solar Document Parse: PDF 바이트 → (마크다운, 요소 배열).

        Upstage Document Digitization API. 마크다운은 content.markdown을
        사용하되 스키마 변동에 대비해 markdown→text→html 순으로 폴백.
        요소 배열(문단/표/수식/헤딩 분류)은 청킹의 1순위 입력이다.
        """
        async with httpx.AsyncClient(
            base_url=self._base, headers=self._headers, timeout=_PARSE_TIMEOUT
        ) as c:
            resp = await _post_retrying(
                c,
                "/document-digitization",
                files={"document": (filename, file_bytes, "application/pdf")},
                data={
                    "model": settings.DOCUMENT_PARSE_MODEL,
                    "output_formats": '["markdown"]',
                    "ocr": "auto",
                },
            )
            body = resp.json()
            content = body.get("content", {})
            markdown = content.get("markdown") or content.get("text") or content.get("html") or ""
            return markdown, list(body.get("elements") or [])

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
            resp = await _post_retrying(
                c,
                "/chat/completions",
                json={
                    "model": settings.SOLAR_CHAT_MODEL,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                },
            )
            raw = resp.json()["choices"][0]["message"]["content"]
        return json.loads(raw)


solar_client = SolarClient()
