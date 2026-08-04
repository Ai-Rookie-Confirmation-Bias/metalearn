"""Upstage Solar 통신 구현체 (OpenAI 호환 API). MVP 메인 생성 엔진."""
import httpx

from app.core.config import settings
from app.core.llm.base import LLMClient

# 팀 결정: 업스테이지 최신 모델을 쓴다. 호출측에서 model=로 덮을 수 있다.
DEFAULT_MODEL = "solar-pro3"
# 학습 블록 한 절 생성이 5~7초 걸린다. httpx 기본(5초)이면 매번 끊긴다.
TIMEOUT = httpx.Timeout(180.0, connect=10.0)


class SolarClient(LLMClient):
    def __init__(self) -> None:
        self._headers = {"Authorization": f"Bearer {settings.UPSTAGE_API_KEY}"}
        self._base = settings.SOLAR_BASE_URL

    async def generate(self, prompt: str, **kwargs: object) -> str:
        """프롬프트로 텍스트 생성.

        kwargs로 `model` · `temperature` · `response_format` · `max_tokens`를
        넘길 수 있다. JSON을 받아야 하는 호출은 `response_format`을 꼭 준다 —
        안 주면 모델이 코드펜스나 설명을 앞뒤에 붙여 파싱이 깨진다.
        """
        body: dict[str, object] = {
            "model": kwargs.get("model") or DEFAULT_MODEL,
            "messages": [{"role": "user", "content": prompt}],
        }
        for key in ("temperature", "response_format", "max_tokens"):
            if kwargs.get(key) is not None:
                body[key] = kwargs[key]

        async with httpx.AsyncClient(
            base_url=self._base, headers=self._headers, timeout=TIMEOUT
        ) as c:
            resp = await c.post("/chat/completions", json=body)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(
            base_url=self._base, headers=self._headers, timeout=TIMEOUT
        ) as c:
            resp = await c.post(
                "/embeddings",
                json={"model": "embedding-query", "input": text},
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]


solar_client = SolarClient()
