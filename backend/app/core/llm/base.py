"""LLM 공통 인터페이스 — 구현체(solar 등)가 따르는 추상 계약.

parse_document는 여기에 두지 않는다. Upstage Document Digitization 전용이라
다른 제공자가 구현할 수 없고, LLM 계약이 아니라 문서 어댑터의 일이다.
"""
from abc import ABC, abstractmethod
from typing import Any


class LLMClient(ABC):
    @abstractmethod
    async def generate(self, prompt: str, **kwargs: object) -> str:
        """프롬프트로 텍스트 생성."""

    @abstractmethod
    async def embed(self, text: str, **kwargs: object) -> list[float]:
        """텍스트 임베딩 벡터 반환 (pgvector 저장용). kwargs: purpose=query|passage."""

    # ── 선택 확장 ────────────────────────────────────────────────────
    #
    # 아래 둘은 generate·embed **위에 얹은 편의**다. 제공자가 반드시 져야 할
    # 의무가 아니라서 추상으로 두지 않는다.
    #
    # ⚠️ 한때 추상이었고, quiz 병합에서 그 대가를 치렀다. 심판 전용
    #    `ExaoneClient`는 generate·embed만 있으면 되는데 두 메서드가 없다고
    #    **모듈 최상단 인스턴스 생성이 TypeError로 죽었고**, quiz 라우터 →
    #    api.py → main.py 로 번져 **앱 전체가 안 떴다.** 가짜 LLM을 쓰는
    #    테스트 스텁 15개도 같은 이유로 무너졌다.
    #    임베딩도 안 하는 심판 모델에게 임베딩 배치를 강제할 이유는 없다.
    #
    # 기본 구현은 조용히 넘기지 않고 **명시적으로 거절한다.** 빈 값을
    # 돌려주면 안 한 일이 한 일처럼 보인다.

    async def generate_json(
        self, prompt: str, *, system: str | None = None
    ) -> dict[str, Any]:
        """JSON 객체를 강제로 받아 dict로 반환. 목차 분류·개념 추출용."""
        raise NotImplementedError(f"{type(self).__name__}은 JSON 강제 모드를 지원하지 않는다")

    async def embed_batch(
        self, texts: list[str], *, purpose: str = "query"
    ) -> list[list[float]]:
        """여러 텍스트를 한 호출로 임베딩. 입력 순서대로 반환."""
        raise NotImplementedError(f"{type(self).__name__}은 임베딩 배치를 지원하지 않는다")
