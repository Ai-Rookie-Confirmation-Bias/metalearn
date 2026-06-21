"""LLM 공통 인터페이스 — 구현체(solar 등)가 따르는 추상 계약."""
from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    async def generate(self, prompt: str, **kwargs: object) -> str:
        """프롬프트로 텍스트 생성."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """텍스트 임베딩 벡터 반환 (pgvector 저장용)."""
