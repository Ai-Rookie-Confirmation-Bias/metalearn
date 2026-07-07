"""Upstage Solar 통신 구현체 (OpenAI 호환 API). 메인 생성·임베딩 엔진."""
from __future__ import annotations

import asyncio
import logging

import httpx

from app.core.config import settings
from app.core.llm.base import LLMClient

logger = logging.getLogger(__name__)

_RETRYABLE = {429, 500, 502, 503, 504}
_MAX_RETRIES = 4
_TIMEOUT = 120.0
_MAX_CONCURRENT = 8  # 프로세스 전역 동시 요청 상한 — 챕터 병렬 생성 시 429 방지


class SolarClient(LLMClient):
    def __init__(self) -> None:
        self._headers = {
            "Authorization": f"Bearer {settings.UPSTAGE_API_KEY}",
            "Content-Type": "application/json",
        }
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
                timeout=_TIMEOUT,
            )
        return self._client

    async def aclose(self) -> None:
        """앱 종료 시 커넥션 풀 정리(main.py lifespan에서 호출)."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def _post(self, path: str, payload: dict) -> dict:
        # 세마포어는 백오프 sleep 동안에도 잡는다 — 429 상황에서 신규 유입까지 줄이는 의도.
        async with self._sem:
            return await self._post_with_retry(path, payload)

    async def _post_with_retry(self, path: str, payload: dict) -> dict:
        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            resp = await self._get_client().post(path, json=payload)

            if resp.status_code in _RETRYABLE:
                wait = 2**attempt
                logger.warning(
                    "Solar %s — %ds 후 재시도 (%d/%d)",
                    resp.status_code,
                    wait,
                    attempt + 1,
                    _MAX_RETRIES,
                )
                last_error = httpx.HTTPStatusError(
                    f"Solar {resp.status_code}",
                    request=resp.request,
                    response=resp,
                )
                await asyncio.sleep(wait)
                continue

            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                body = resp.text[:500]
                raise RuntimeError(f"Solar API 오류 {resp.status_code}: {body}") from exc

            return resp.json()

        assert last_error is not None
        raise last_error

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

        data = await self._post("/chat/completions", payload)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Solar 응답 파싱 실패: {data}") from exc

    async def embed(self, text: str, **kwargs: object) -> list[float]:
        purpose = str(kwargs.get("purpose", "query"))
        model = (
            settings.SOLAR_EMBED_PASSAGE_MODEL
            if purpose == "passage"
            else settings.SOLAR_EMBED_QUERY_MODEL
        )
        data = await self._post(
            "/embeddings",
            {"model": model, "input": text},
        )
        try:
            return data["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Solar embedding 파싱 실패: {data}") from exc


solar_client = SolarClient()
