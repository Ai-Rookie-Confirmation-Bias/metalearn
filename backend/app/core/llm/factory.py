"""LLM 클라이언트 선택: Solar > mock."""
from app.core.config import settings
from app.core.llm.base import LLMClient
from app.core.llm.mock import mock_client
from app.core.llm.solar import solar_client


def get_llm_client() -> LLMClient:
    if settings.llm_provider == "solar":
        return solar_client
    return mock_client
