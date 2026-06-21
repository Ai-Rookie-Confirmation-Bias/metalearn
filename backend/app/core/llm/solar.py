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

    async def generate(self, prompt: str, **kwargs: object) -> str:
        async with httpx.AsyncClient(base_url=self._base, headers=self._headers) as c:
            resp = await c.post(
                "/chat/completions",
                json={
                    "model": "solar-pro2",
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
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
