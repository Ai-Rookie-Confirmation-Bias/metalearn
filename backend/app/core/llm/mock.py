"""API 키 없이 개발·테스트할 때 쓰는 Mock LLM.

Solar 연동 전에 seed/materials 플로우를 end-to-end로 검증한다.
"""
import json
import random

from app.core.llm.base import LLMClient

_EMBED_DIM = 4096


class MockLLMClient(LLMClient):
    async def generate(self, prompt: str, **kwargs: object) -> str:
        if "진단" in prompt or "diagnostic" in prompt.lower():
            return json.dumps(
                {
                    "questions": [
                        {
                            "concept_id": "c1",
                            "question_text": "다음 중 해당 개념의 핵심 설명으로 가장 적절한 것은?",
                            "options": ["정답 후보", "오답 A", "오답 B", "오답 C"],
                            "correct_index": 0,
                        }
                    ]
                },
                ensure_ascii=False,
            )
        return f"[mock] {prompt[:120]}"

    async def embed(self, text: str) -> list[float]:
        # 결정적 pseudo-embedding (pgvector 저장 테스트용)
        seed = sum(ord(c) for c in text[:200])
        rng = random.Random(seed)
        return [rng.uniform(-0.1, 0.1) for _ in range(_EMBED_DIM)]


mock_client = MockLLMClient()
