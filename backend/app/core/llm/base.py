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
    async def generate_json(
        self, prompt: str, *, system: str | None = None
    ) -> dict[str, Any]:
        """JSON 객체를 강제로 받아 dict로 반환. 목차 분류·개념 추출용."""

    @abstractmethod
    async def embed(self, text: str, **kwargs: object) -> list[float]:
        """텍스트 임베딩 벡터 반환 (pgvector 저장용). kwargs: purpose=query|passage."""

    @abstractmethod
    async def embed_batch(
        self, texts: list[str], *, purpose: str = "query"
    ) -> list[list[float]]:
        """여러 텍스트를 한 호출로 임베딩. 입력 순서대로 반환."""
