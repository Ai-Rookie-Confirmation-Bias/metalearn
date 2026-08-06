"""EXAONE 통신 구현체 (OpenAI 호환 API) — 교차 모델 검증용.

생성(Solar)과 다른 계열 모델로 심판·풀이를 시키면 같은 모델이 같은 실수를
같이 놓치는 상관 오류를 줄인다 (QUIZ_TUNING §7의 'sN 전멸 조각' 패턴).
기본 엔드포인트는 FriendliAI serverless — 다른 제공자면 .env에서
EXAONE_BASE_URL / EXAONE_MODEL만 바꾸면 된다.
"""
import asyncio
import time
from collections import deque

import httpx

from app.core.config import settings
from app.core.llm.base import LLMClient

# friendli serverless 무료 티어 실측: 분당 3요청 (x-ratelimit-limit-requests: 3,
# reset 60s). 사전 스로틀 없이 돌리면 검증 배치가 429로 죽는다.
_RATE_LIMIT = 3
_RATE_WINDOW = 62.0  # 리셋 60s + 여유


class ExaoneClient(LLMClient):
    def __init__(self) -> None:
        self._base = settings.EXAONE_BASE_URL
        self._model = settings.EXAONE_MODEL
        self._call_times: deque[float] = deque(maxlen=_RATE_LIMIT)
        self._throttle = asyncio.Lock()

    async def _wait_for_slot(self) -> None:
        """슬라이딩 윈도 스로틀 — 최근 60초 호출이 한도에 차면 슬롯이 빌 때까지 대기.

        분당 3회 제한은 serverless 티어 실측값 — dedicated 엔드포인트에선 불필요.
        """
        if "serverless" not in self._base:
            return
        async with self._throttle:
            now = time.monotonic()
            if len(self._call_times) == _RATE_LIMIT:
                elapsed = now - self._call_times[0]
                if elapsed < _RATE_WINDOW:
                    await asyncio.sleep(_RATE_WINDOW - elapsed)
            self._call_times.append(time.monotonic())

    async def generate(self, prompt: str, **kwargs: object) -> str:
        headers = {"Authorization": f"Bearer {settings.EXAONE_API_KEY}"}
        async with httpx.AsyncClient(
            base_url=self._base, headers=headers, timeout=120.0
        ) as c:
            body = {
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                # K-EXAONE은 추론 모델 — friendli serverless는 completion을
                # 2,000토큰에서 자르는데 추론이 이를 다 소진하면 content가
                # 아예 안 온다(finish=length). 검증 출력은 JSON 판정이라
                # 추론을 끄고 즉답을 받는다.
                "chat_template_kwargs": {"enable_thinking": False},
            }
            for attempt in range(6):
                await self._wait_for_slot()
                resp = await c.post("/chat/completions", json=body)
                if resp.status_code in (429, 503) and attempt < 5:
                    # 스로틀을 뚫고 온 429 — 윈도 리셋까지 대기 후 재시도
                    wait = float(
                        resp.headers.get("Retry-After")
                        or resp.headers.get("x-ratelimit-reset-requests")
                        or 20
                    )
                    await asyncio.sleep(min(wait + 1.0, 70.0))
                    continue
                break
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            content = choice["message"].get("content") or ""
            if not content.strip():
                raise RuntimeError(
                    f"EXAONE 빈 응답 (finish_reason={choice.get('finish_reason')})"
                )
            return content

    async def embed(self, text: str) -> list[float]:
        raise NotImplementedError("EXAONE 클라이언트는 검증용 — 임베딩은 Solar 사용")


exaone_client = ExaoneClient()
