"""Upstage Solar 통신 구현체 (OpenAI 호환 API). 메인 생성·임베딩 엔진.

- generate / generate_json / embed / embed_batch : LLMClient 계약 구현
- parse_document                                 : Upstage Document Digitization 전용

파싱 파이프라인은 조각 수십 개를 동시에 던지므로 두 장치가 필수다:
  - 공유 커넥션 풀 + 전역 세마포어 → 매 호출 TCP+TLS 재수립 방지, 429 사전 차단
  - 지수 백오프 재시도(Retry-After 존중) → 429·게이트웨이 5xx 흡수
둘 중 하나라도 없으면 개념 추출(조각당 1콜) 단계에서 파이프라인 전체가 죽는다.
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
# 문서 파싱은 페이지가 많으면 더 길어진다.
_GEN_TIMEOUT = 120.0
_BATCH_TIMEOUT = 240.0
_PARSE_TIMEOUT = 180.0

_TRANSIENT_RETRIES = 5
_TRANSIENT_STATUS = {429, 500, 502, 503, 504}

# 프로세스 전역 동시 요청 상한 — 조각 병렬 추출 시 429 방지.
# 실측 두 점: 40 동시 = 즉시 429 (PARSING_PLAN) / 8 = 안전. 전면 병렬 실험으로
# 24까지 올림 — 429가 뜨면 _post_retrying 백오프가 흡수하지만, 재시도 로그가
# 잦으면 이 값을 내리는 게 맞다.
_MAX_CONCURRENT = 24


def _strip_nul(value: Any) -> Any:
    """LLM 응답에서 NUL 문자를 걷어낸다.

    PostgreSQL은 text·JSONB에 \\u0000을 저장하지 못한다. 그런데 교재가
    C 문자열이나 널 종료를 설명하면 LLM이 널 문자를 그대로 뱉는다.
    실측: 정처기 필기 교재의 "문자열은 널 문자('\\0')로 끝난다" 대목에서
    개념 저장이 DataError로 통째로 죽었다.

    LLM JSON이 들어오는 유일한 길목이라 여기서 한 번만 막으면 된다.
    """
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, dict):
        return {k: _strip_nul(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_strip_nul(v) for v in value]
    return value


async def _post_retrying(
    client: httpx.AsyncClient, url: str, **kwargs: Any
) -> httpx.Response:
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
            logger.warning(
                "Upstage %s %s — %.0fs 후 재시도(%d/%d)",
                url, type(exc).__name__, delay, attempt + 1, _TRANSIENT_RETRIES,
            )
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
        logger.warning(
            "Upstage %s HTTP %d — %.0fs 후 재시도(%d/%d)",
            url, resp.status_code, delay, attempt + 1, _TRANSIENT_RETRIES,
        )
        await asyncio.sleep(delay)

    raise AssertionError("unreachable")


class SolarClient(LLMClient):
    def __init__(self) -> None:
        self._headers = {"Authorization": f"Bearer {settings.UPSTAGE_API_KEY}"}
        self._base = settings.SOLAR_BASE_URL
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
        """앱 종료 시 커넥션 풀 정리 (main.py lifespan에서 호출)."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def _request(self, url: str, **kwargs: Any) -> httpx.Response:
        """세마포어(전역 동시성 상한) 안에서 재시도 포함 POST.

        세마포어는 백오프 sleep 동안에도 잡는다 — 429 상황에서 신규 유입까지
        줄이려는 의도. 슬롯을 놓아주면 대기 중이던 요청이 즉시 밀려들어간다.
        """
        async with self._sem:
            return await _post_retrying(self._get_client(), url, **kwargs)

    # ── 생성 ──────────────────────────────────────────────────────

    async def generate(self, prompt: str, **kwargs: object) -> str:
        """프롬프트로 텍스트 생성.

        `model` · `temperature` · `response_format` · `max_tokens`를 kwargs로
        덮을 수 있다. `json_mode=True`는 `response_format`의 짧은 표기다.

        ⚠️ **`response_format`을 안 받으면 커리큘럼 파서가 통째로 깨진다.**
           학습 블록 에이전트 네 곳이 JSON을 받아야 하는데, 안 주면 모델이
           코드펜스나 설명을 앞뒤에 붙인다 — 그리고 그건 조용히 일어난다.
        """
        payload: dict[str, Any] = {
            "model": str(kwargs.get("model") or settings.SOLAR_CHAT_MODEL),
            "messages": [{"role": "user", "content": prompt}],
            # 호출측이 정하면 그걸 쓰고, 아니면 파싱이 쓰던 0.3.
            "temperature": kwargs.get("temperature", 0.3),
        }
        if kwargs.get("json_mode"):
            payload["response_format"] = {"type": "json_object"}
        for key in ("response_format", "max_tokens"):
            if kwargs.get(key) is not None:
                payload[key] = kwargs[key]

        resp = await self._request("/chat/completions", json=payload)
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Solar 응답 파싱 실패: {data}") from exc

    async def generate_json(
        self, prompt: str, *, system: str | None = None, timeout: float = _GEN_TIMEOUT
    ) -> dict[str, Any]:
        """JSON 객체를 강제로 받아 dict로 파싱.

        response_format=json_object로 비정형 텍스트 혼입을 1차 차단하고,
        호출부(pipeline/prompts)에서 스키마 검증으로 2차 방어한다.
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
        return _strip_nul(json.loads(raw))

    # ── 임베딩 ────────────────────────────────────────────────────

    @staticmethod
    def _embed_model(purpose: str) -> str:
        """비대칭 임베딩 — 개념명은 query, 원문 조각은 passage 모델."""
        return (
            settings.SOLAR_EMBED_PASSAGE_MODEL
            if purpose == "passage"
            else settings.SOLAR_EMBED_QUERY_MODEL
        )

    async def embed(self, text: str, **kwargs: object) -> list[float]:
        model = self._embed_model(str(kwargs.get("purpose", "query")))
        resp = await self._request("/embeddings", json={"model": model, "input": text})
        data = resp.json()
        try:
            return data["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Solar embedding 파싱 실패: {data}") from exc

    async def embed_batch(
        self, texts: list[str], *, purpose: str = "query"
    ) -> list[list[float]]:
        """여러 텍스트를 한 호출로 임베딩. 입력 순서대로 반환.

        응답의 index 필드로 정렬해 순서를 보장한다 — 조각/개념과 벡터가
        어긋나면 전혀 다른 내용에 임베딩이 붙는다.
        """
        if not texts:
            return []
        resp = await self._request(
            "/embeddings",
            json={"model": self._embed_model(purpose), "input": texts},
            timeout=_BATCH_TIMEOUT,
        )
        data = sorted(resp.json()["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in data]

    # ── 문서 파싱 ─────────────────────────────────────────────────

    async def parse_document(
        self, file_bytes: bytes, filename: str, *, content_type: str = "application/pdf"
    ) -> tuple[str, list[dict[str, Any]]]:
        """Document Parse: 파일 바이트 → (마크다운, 요소 배열).

        요소 배열이 파싱 파이프라인의 1순위 입력이다 — 마크다운은 폴백/디버깅용.
        content.markdown 스키마 변동에 대비해 markdown→text→html 순으로 폴백한다.

        base64_encoding으로 figure/chart 크롭 이미지를 함께 받는다. AI가 그림을
        그리는 게 아니라 원문에서 잘라오는 것이라 환각이 0이다.
        """
        resp = await self._request(
            "/document-digitization",
            files={"document": (filename, file_bytes, content_type)},
            data={
                "model": settings.DOCUMENT_PARSE_MODEL,
                "output_formats": '["markdown"]',
                "ocr": "auto",
                "base64_encoding": '["figure", "chart"]',
            },
            timeout=_PARSE_TIMEOUT,
        )
        body = resp.json()
        content = body.get("content") or {}
        markdown = (
            content.get("markdown") or content.get("text") or content.get("html") or ""
        )
        return markdown, list(body.get("elements") or [])


solar_client = SolarClient()
