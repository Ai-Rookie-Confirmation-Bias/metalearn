"""[2.DTO] 섭취 도메인 입출력 + LLM 추출 스키마.

추출 스키마(ConceptNode/ExtractionResult)는 LLM JSON 출력의 2차 검증 게이트다.
명세의 "N-2 깊이 제한"을 재귀 절단으로 강제한다 — LLM이 깊이 규칙을 어겨도
상한(depth 2) 초과 하위 노드는 자동 제거해 섭취가 실패하지 않게 한다.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.core.config import settings


# ── LLM 추출(extraction) 스키마 ──────────────────────────────────────────────
class ConceptNode(BaseModel):
    """LLM이 추출하는 개념 노드. prerequisites가 직접 선수지식(서브트리)."""

    name: str = Field(..., min_length=1, max_length=256, description="개념 이름(고유)")
    description: str = Field(..., min_length=1, description="개념 한 줄 설명")
    prerequisites: list[ConceptNode] = Field(
        default_factory=list, description="직접 선수 개념들"
    )


def truncate_concept_tree(node: ConceptNode, depth: int = 0) -> ConceptNode:
    """개념 트리를 MAX_CONCEPT_DEPTH 이내로 절단한다.

    depth >= max_depth 인 노드의 prerequisites 는 비워 더 깊은 하위를 제거한다.
    예) max_depth=2 이면 depth 0·1·2 노드는 유지, depth 3+(IP 등)은 삭제.
    """
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
    """추출 최상위: 타겟 개념(루트)들의 목록."""

    concepts: list[ConceptNode] = Field(default_factory=list)

    @model_validator(mode="after")
    def _truncate_depth_limit(self) -> ExtractionResult:
        self.concepts = [truncate_concept_tree(root) for root in self.concepts]
        return self


# ── 응답 DTO ────────────────────────────────────────────────────────────────
class PrerequisiteEdgeOut(BaseModel):
    prerequisite_concept_id: int


class ConceptOut(BaseModel):
    id: int
    name: str
    description: str
    depth: int
    prerequisite_ids: list[int] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class MaterialSummary(BaseModel):
    id: int
    title: str
    filename: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MaterialDetail(MaterialSummary):
    concept_count: int
    concepts: list[ConceptOut] = Field(default_factory=list)
