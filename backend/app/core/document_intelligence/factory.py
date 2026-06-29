"""문서 지능 provider: Solar LLM 또는 local."""
from app.core.config import settings
from app.core.document_intelligence.base import DocumentIntelligence
from app.core.document_intelligence.local import LocalDocumentIntelligence
from app.core.document_intelligence.llm import LLMDocumentIntelligence
from app.core.llm.factory import get_llm_client


def get_document_intelligence() -> DocumentIntelligence:
    if settings.use_mock_ai:
        return LocalDocumentIntelligence()
    return LLMDocumentIntelligence(get_llm_client())
