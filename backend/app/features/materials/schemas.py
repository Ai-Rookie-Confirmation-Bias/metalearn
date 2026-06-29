"""[2.DTO] materials 입출력."""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TocEntry(BaseModel):
    id: str
    title: str
    start_page: int
    end_page: int


class ConceptEntry(BaseModel):
    id: str
    title: str
    page_numbers: list[int]
    chunk_ids: list[str]
    prior_concept_ids: list[str] = Field(default_factory=list)


class DocumentSkeleton(BaseModel):
    document_id: uuid.UUID
    page_count: int
    toc: list[TocEntry]
    concepts: list[ConceptEntry]
    external_prerequisites: list[str] = Field(
        default_factory=list,
        description="PDF 밖 선행지식 후보 (설문 2단계용)",
    )


class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    page_count: int
    parse_status: str
    parse_engine: Literal["upstage", "pypdf"] = "pypdf"
    parse_mode: Literal["llm", "local"] = "local"
    created_at: datetime

    model_config = {"from_attributes": True}


class ChunkPreview(BaseModel):
    id: uuid.UUID
    page_number: int
    preview: str
