"""EXAONE 통신 구현체 (OpenAI 호환 API) — 교차 모델 검증용.

생성(Solar)과 다른 계열 모델로 심판·풀이를 시키면 같은 모델이 같은 실수를
같이 놓치는 상관 오류를 줄인다 (QUIZ_TUNING §7의 'sN 전멸 조각' 패턴).
기본 엔드포인트는 FriendliAI serverless — 다른 제공자면 .env에서
EXAONE_BASE_URL / EXAONE_MODEL만 바꾸면 된다.
"""
import httpx

from app.core.config import settings
from app.core.llm.base import LLMClient


class ExaoneClient(LLMClient):
    def __init__(self) -> None:
        self._base = settings.EXAONE_BASE_URL
        self._model = settings.EXAONE_MODEL

    async def generate(self, prompt: str, **kwargs: object) -> str:
        headers = {"Authorization": f"Bearer {settings.EXAONE_API_KEY}"}
        async with httpx.AsyncClient(
            base_url=self._base, headers=headers, timeout=120.0
        ) as c:
            resp = await c.post(
                "/chat/completions",
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    async def embed(self, text: str) -> list[float]:
        raise NotImplementedError("EXAONE 클라이언트는 검증용 — 임베딩은 Solar 사용")


exaone_client = ExaoneClient()
