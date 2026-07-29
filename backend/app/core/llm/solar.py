"""Upstage Solar 통신 구현체 (OpenAI 호환 API). MVP 메인 생성 엔진.

실제 호출은 features/service에서 사용. 지금은 골격 + 호출 형태만.
"""
import httpx

from app.core.config import settings
from app.core.llm.base import LLMClient


class SolarClient(LLMClient):
    def __init__(self) -> None:
        self._headers = {"Authorization": f"Bearer {settings.UPSTAGE_API_KEY}"}
        self._base = settings.SOLAR_BASE_URL
        self._model = settings.SOLAR_MODEL

    async def generate(self, prompt: str, **kwargs: object) -> str:
        # 선택 파라미터(response_format·temperature 등)는 kwargs로 그대로 전달.
        # 문제 생성 에이전트는 response_format={"type":"json_object"}로 JSON을 강제한다.
        # model은 settings 기본값을 쓰되 호출측 kwargs로 개별 override 가능.
        body: dict[str, object] = {
            "model": kwargs.get("model", self._model),
            "messages": [{"role": "user", "content": prompt}],
        }
        for key in ("response_format", "temperature", "max_tokens"):
            if key in kwargs:
                body[key] = kwargs[key]
        async with httpx.AsyncClient(
            base_url=self._base, headers=self._headers, timeout=120.0
        ) as c:
            resp = await c.post("/chat/completions", json=body)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(base_url=self._base, headers=self._headers) as c:
            resp = await c.post(
                "/embeddings",
                json={"model": "embedding-query", "input": text},
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]


solar_client = SolarClient()
