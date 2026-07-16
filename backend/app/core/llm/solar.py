"""Upstage Solar 통신 구현체 (OpenAI 호환 API). 메인 생성·임베딩 엔진.

- generate / embed: LLMClient 계약 구현 (온/오프라인 패리티 대상)
- embed_batch / parse_document / generate_json: Solar 전용 확장 (클라우드 전용, Ingestion용)

병합 통합본(backend-ai-core + parsing):
  - 공유 커넥션 풀(keep-alive) + 전역 동시성 세마포어 = backend-ai-core (성능 튜닝)
  - 일시오류 백오프 재시도(_post_retrying, Retry-After 존중) = parsing (더 견고한 쪽 채택)
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.core.llm.base import LLMClient

# uvicorn 핸들러를 상속해 docker logs에서 바로 보이도록 (진행 관찰용)
logger = logging.getLogger("uvicorn.error")

# 외부 API 타임아웃(초). solar-pro3는 추론형이라 단일 생성이 길어질 수 있어 넉넉히.
# 문서 파싱은 페이지가 많으면 더 길어질 수 있음.
_GEN_TIMEOUT = 120.0
_BATCH_TIMEOUT = 240.0
_PARSE_TIMEOUT = 180.0

# 일시 오류 백오프 재시도. 섹션 분할 추출로 호출량이 늘어(특히 배치 embed)
# 429 rate limit과 게이트웨이 5xx를 흡수할 장치가 필요 (parsing ISSUE-008).
_TRANSIENT_RETRIES = 5
_TRANSIENT_STATUS = {429, 500, 502, 503, 504}

# 프로세스 전역 동시 요청 상한 — 챕터 병렬 생성 시 429 방지
_MAX_CONCURRENT = 8


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
            logger.warning("Upstage %s %s — %.0fs 후 재시도(%d/%d)", url, type(exc).__name__, delay, attempt + 1, _TRANSIENT_RETRIES)
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
        logger.warning("Upstage %s HTTP %d — %.0fs 후 재시도(%d/%d)", url, resp.status_code, delay, attempt + 1, _TRANSIENT_RETRIES)
        await asyncio.sleep(delay)
    raise AssertionError("unreachable")


class SolarClient(LLMClient):
    def __init__(self) -> None:
        self._headers = {"Authorization": f"Bearer {settings.UPSTAGE_API_KEY}"}
        self._base = settings.SOLAR_BASE_URL
        self._model = settings.SOLAR_MODEL
        self._client: httpx.AsyncClient | None = None
        self._sem = asyncio.Semaphore(_MAX_CONCURRENT)

    def _get_client(self) -> httpx.AsyncClient:
        """공유 커넥션 풀(keep-alive) — 콜마다 TCP+TLS 핸드셰이크 반복 방지."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base,
                headers=self._headers,
                timeout=_GEN_TIMEOUT,
            )
        return self._client

    async def aclose(self) -> None:
        """앱 종료 시 커넥션 풀 정리(main.py lifespan에서 호출)."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def _request(self, url: str, **kwargs: Any) -> httpx.Response:
        """세마포어(전역 동시성 상한) 안에서 재시도 포함 POST.

        세마포어는 백오프 sleep 동안에도 잡는다 — 429 상황에서 신규 유입까지 줄이는 의도.
        """
        async with self._sem:
            return await _post_retrying(self._get_client(), url, **kwargs)

    async def generate(self, prompt: str, **kwargs: object) -> str:
        model = str(kwargs.get("model") or self._model)
        json_mode = bool(kwargs.get("json_mode", False))

        payload: dict = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        resp = await self._request("/chat/completions", json=payload)
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Solar 응답 파싱 실패: {data}") from exc

    async def generate_json(
        self, prompt: str, *, system: str | None = None, timeout: float = _GEN_TIMEOUT
    ) -> dict[str, Any]:
        """JSON 객체를 강제로 받아 dict로 파싱 (parsing Ingestion용).

        response_format=json_object로 비정형 텍스트/할루시네이션 혼입을 1차 차단하고,
        호출부(service)에서 Pydantic 스키마로 2차 검증한다.
        """
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = await self._request(
            "/chat/completions",
            json={
                "model": settings.SOLAR_CHAT_MODEL,
                "messages": messages,
                "response_format": {"type": "json_object"},
            },
            timeout=timeout,
        )
        raw = resp.json()["choices"][0]["message"]["content"]
        return json.loads(raw)

    async def embed(self, text: str, **kwargs: object) -> list[float]:
        purpose = str(kwargs.get("purpose", "query"))
        model = (
            settings.SOLAR_EMBED_PASSAGE_MODEL
            if purpose == "passage"
            else settings.SOLAR_EMBED_QUERY_MODEL
        )
        resp = await self._request("/embeddings", json={"model": model, "input": text})
        data = resp.json()
        try:
            return data["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Solar embedding 파싱 실패: {data}") from exc

    async def embed_batch(
        self, texts: list[str], *, purpose: str = "query"
    ) -> list[list[float]]:
        """여러 텍스트를 한 호출로 임베딩 (parsing ISSUE-010: 개념당 1호출 → 배치).

        입력 순서대로 반환한다 (응답의 index 필드로 정렬 보장).
        purpose="passage"면 청크용 passage 모델 사용(ISSUE-015 비대칭 임베딩).
        """
        model = (
            settings.SOLAR_EMBED_PASSAGE_MODEL
            if purpose == "passage"
            else settings.SOLAR_EMBED_QUERY_MODEL
        )
        resp = await self._request(
            "/embeddings",
            json={"model": model, "input": texts},
            timeout=_BATCH_TIMEOUT,
        )
        data = sorted(resp.json()["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in data]

    async def parse_document(
        self, file_bytes: bytes, filename: str
    ) -> tuple[str, list[dict[str, Any]]]:
        """Solar Document Parse: PDF 바이트 → (마크다운, 요소 배열).

        Upstage Document Digitization API. 마크다운은 content.markdown을
        사용하되 스키마 변동에 대비해 markdown→text→html 순으로 폴백.
        요소 배열(문단/표/수식/헤딩 분류)은 청킹의 1순위 입력이다.
        """
        resp = await self._request(
            "/document-digitization",
            files={"document": (filename, file_bytes, "application/pdf")},
            data={
                "model": settings.DOCUMENT_PARSE_MODEL,
                "output_formats": '["markdown"]',
                "ocr": "auto",
                # 교재 그림·도표를 크롭 이미지(base64)로 함께 받는다(Layer 2 —
                # 원문 이미지 재사용: AI가 그리는 게 아니라 원문에서 추출, 환각 0).
                # 실증(2026-07-16): figure 요소에 base64_encoding 필드로 옴.
                "base64_encoding": '["figure", "chart"]',
            },
            timeout=_PARSE_TIMEOUT,
        )
        body = resp.json()
        content = body.get("content", {})
        markdown = content.get("markdown") or content.get("text") or content.get("html") or ""
        return markdown, list(body.get("elements") or [])


solar_client = SolarClient()
