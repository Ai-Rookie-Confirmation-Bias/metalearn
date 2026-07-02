"""[2.DTO] 섭취 도메인 입출력 + LLM 추출 스키마."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.core.config import settings


class ConceptNode(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    description: str = Field(..., min_length=1)
    prerequisites: list[ConceptNode] = Field(default_factory=list)


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


class ExtractionResult(BaseModel):
    concepts: list[ConceptNode] = Field(default_factory=list)

    @model_validator(mode="after")
    def _truncate_depth_limit(self) -> ExtractionResult:
        self.concepts = [truncate_concept_tree(root) for root in self.concepts]
        return self


class ConceptOut(BaseModel):
    id: int
    name: str
    description: str
    depth_level: int
    prerequisite_ids: list[int] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class CourseSummary(BaseModel):
    id: int
    document_id: int
    title: str
    filename: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CourseDetail(BaseModel):
    id: int
    document_id: int
    title: str
    filename: str
    status: str
    created_at: datetime
    concept_count: int
    concepts: list[ConceptOut] = Field(default_factory=list)
