"""Document Parse provider: Upstage > pypdf."""
from app.core.config import settings
from app.core.document_parse.base import DocumentParser
from app.core.document_parse.local import LocalDocumentParser
from app.core.document_parse.upstage import UpstageDocumentParser


def get_document_parser() -> DocumentParser:
    if settings.UPSTAGE_API_KEY.strip():
        return UpstageDocumentParser()
    return LocalDocumentParser()
