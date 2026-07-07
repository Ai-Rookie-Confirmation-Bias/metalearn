"""[2.DTO] 섭취 도메인 입출력 + LLM 추출 스키마. (병합 2단계: id는 UUID)"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import settings


class ConceptNode(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    description: str = Field(..., min_length=1)
    prerequisites: list[ConceptNode] = Field(default_factory=list)

    @field_validator("prerequisites", mode="before")
    @classmethod
    def _coerce_str_prerequisites(cls, v: object) -> object:
        """LLM이 선수개념을 객체 대신 문자열로 반환하는 형식 이탈 보정."""
        if isinstance(v, list):
            return [
                {"name": item, "description": item} if isinstance(item, str) else item
                for item in v
            ]
        return v


def truncate_concept_tree(node: ConceptNode, depth: int = 0) -> ConceptNode:
    max_depth = settings.MAX_CONCEPT_DEPTH
    if depth >= max_depth:
        return node.model_copy(update={"prerequisites": []})
    return node.model_copy(
        update={
            "prerequisites": [
                truncate_concept_tree(child, depth + 1) for child in node.prerequisites
            ]
        }
    )


class SectionConcept(BaseModel):
    """청크(섹션) 전체를 대표하는 개념 — 조건부 섹션 계층의 depth 0 노드."""

    name: str = Field(..., min_length=1, max_length=256)
    description: str = Field(..., min_length=1)


class ExtractionResult(BaseModel):
    section: SectionConcept | None = None
    concepts: list[ConceptNode] = Field(default_factory=list)

    @model_validator(mode="after")
    def _truncate_depth_limit(self) -> ExtractionResult:
        self.concepts = [truncate_concept_tree(root) for root in self.concepts]
        return self


class ConceptOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    depth_level: int
    source: str = "book"  # 'book' = 교재 추출, 'ai_prereq' = LLM 보충 선수개념
    source_anchor: str | None = None  # 교재 추출 시 원문 섹션(헤딩 경로)
    prerequisite_ids: list[uuid.UUID] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class CourseSummary(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    title: str
    filename: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CourseDetail(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    title: str
    filename: str
    status: str
    created_at: datetime
    concept_count: int
    concepts: list[ConceptOut] = Field(default_factory=list)
