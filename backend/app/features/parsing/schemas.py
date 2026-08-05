"""[DTO] 파이프라인 중간 산출물 + API 입출력.

파이프라인 단계들은 DB 모델이 아니라 여기 정의된 형태를 주고받는다.
그래야 단계 하나를 DB 없이 따로 테스트할 수 있다.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TypeAlias

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import settings

# Document Parse가 돌려주는 요소 하나.
#   {"id": 2, "category": "heading1", "page": 3, "content": {"markdown": "..."}}
# 정제 단계가 여기에 removed 키를 덧붙인다.
Element: TypeAlias = dict[str, Any]


# ─────────────────────────────────────────────────────────────────
# 파이프라인 중간 산출물
# ─────────────────────────────────────────────────────────────────


@dataclass
class Segment:
    """5단계 산출물 — 원문 조각. content는 마크다운 원문 그대로다."""

    seq: int
    content: str
    heading: str | None = None
    element_from: int | None = None
    element_to: int | None = None
    page_from: int | None = None
    page_to: int | None = None

    @property
    def char_count(self) -> int:
        return len(self.content)


@dataclass
class FigureDraft:
    """2단계 산출물 — 그림 크롭 + 주변 원문. 설명은 아직 만들지 않는다."""

    page: int
    element_id: int
    category: str
    mime: str
    data: bytes
    caption: str | None = None
    context_text: str | None = None
    needs_vision: bool = False


@dataclass
class TopicDraft:
    """7단계 산출물 — 목차 하나와 거기 속한 조각 번호들."""

    seq: int
    title: str
    segment_seqs: list[int] = field(default_factory=list)


@dataclass
class TopicAssignment:
    """7단계 전체 산출물. 검산에 필요한 수치를 함께 들고 다닌다."""

    topics: list[TopicDraft]
    total_segments: int

    @property
    def assigned_count(self) -> int:
        return sum(len(t.segment_seqs) for t in self.topics)

    @property
    def is_complete(self) -> bool:
        """조각 수 = 목차별 합계. 이게 원문 무손실의 유일한 보증이다."""
        return self.assigned_count == self.total_segments


# ─────────────────────────────────────────────────────────────────
# 개념 추출 (LLM 응답 스키마)
# ─────────────────────────────────────────────────────────────────


class ConceptNode(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    # description은 필수가 아니다. 실측: 선수개념 하나에서 description이
    # 빠졌다는 이유로 조각 전체의 검증이 깨져 개념 40여 개가 통째로 날아갔다.
    # 설명 한 줄이 없는 것과 조각 하나를 통째로 버리는 것은 피해가 비교가 안 된다.
    description: str = Field(default="")
    # 영문 슬러그. 추출 시 동시 산출이라 추가 비용 0. 빠뜨려도 무해하다
    # (13단계 전역 키 부여가 빈 것만 채운다).
    key: str | None = Field(default=None, max_length=128)
    # 근거 문장 번호 (조각 안에서의 seq). 못 찾으면 빈 배열이 정상이다 —
    # 선수개념은 대개 교재 밖 배경지식이라 원문에 근거가 없다.
    evidence: list[int] = Field(default_factory=list)
    prerequisites: list[ConceptNode] = Field(default_factory=list)

    @model_validator(mode="after")
    def _fill_missing_description(self) -> ConceptNode:
        """설명이 비면 이름으로 대신한다 — 임베딩 입력이 비지 않게."""
        if not self.description.strip():
            self.description = self.name
        return self

    @field_validator("evidence", mode="before")
    @classmethod
    def _coerce_evidence(cls, v: object) -> object:
        """근거 번호를 관대하게 읽는다.

        목차 분류에서 겪은 것과 같은 형식 이탈이다 — 프롬프트가 문장을
        "[3] …"로 보여주니 LLM이 3 대신 "[3]"이나 "3"을 돌려준다. 여기서
        흡수하지 않으면 멀쩡한 근거를 통째로 버린다.
        """
        if v is None:
            return []
        if isinstance(v, (int, str)):
            v = [v]
        if not isinstance(v, list):
            return []
        out: list[int] = []
        for item in v:
            if isinstance(item, bool):
                continue
            if isinstance(item, int):
                out.append(item)
            elif isinstance(item, str):
                digits = item.strip().strip("[]()#<> \t")
                if digits.isdigit():
                    out.append(int(digits))
        return out

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
    """깊이 상한 초과분을 잘라낸다 — 과분할·노이즈 방지."""
    if depth >= settings.MAX_CONCEPT_DEPTH:
        return node.model_copy(update={"prerequisites": []})
    return node.model_copy(
        update={
            "prerequisites": [
                truncate_concept_tree(child, depth + 1) for child in node.prerequisites
            ]
        }
    )


class ExtractionResult(BaseModel):
    """8단계 응답. section 필드가 없다 — 7단계가 이미 목차를 정했다."""

    concepts: list[ConceptNode] = Field(default_factory=list)

    @model_validator(mode="after")
    def _truncate_depth_limit(self) -> ExtractionResult:
        self.concepts = [truncate_concept_tree(root) for root in self.concepts]
        return self


# ─────────────────────────────────────────────────────────────────
# API 입출력
# ─────────────────────────────────────────────────────────────────


class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    source_format: str
    status: str
    error: str | None = None
    parser_version: str
    density_grade: str | None = None
    avg_segment_chars: int | None = None
    concept_coverage: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FigureOut(BaseModel):
    """조각 본문 안에서의 그림 위치.

    char_offset은 조각 content 안에서 이 그림이 원래 있던 지점이다.
    프론트가 본문을 그 지점에서 끊고 이미지를 끼워 넣으면 원문 흐름이 복원된다.
    """

    id: uuid.UUID
    page: int
    element_id: int
    category: str
    caption: str | None = None
    needs_vision: bool = False
    description: str | None = None
    char_offset: int = 0

    model_config = {"from_attributes": True}


class SegmentOut(BaseModel):
    id: uuid.UUID
    seq: int
    heading: str | None = None
    content: str
    page_from: int | None = None
    page_to: int | None = None
    char_count: int
    sentence_count: int = 0
    figures: list[FigureOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class EvidenceOut(BaseModel):
    """개념의 근거 문장 하나 — 원문의 어디인가.

    char_start/end는 **조각 content 안의 offset**이다. 조각이 여러 페이지에
    걸치는 일이 흔해서(실측: 조각 0 = p.1~4) 문장 하나의 정확한 페이지는
    지금 데이터로 특정할 수 없다. 그래서 페이지는 조각의 범위를 그대로 주고,
    정확한 좌표는 조각 기준으로 준다 — 화면이 조각 본문을 통째로 받아
    이 구간만 강조하면 원문 대조가 정확히 맞는다.
    """

    segment_seq: int
    sentence_seq: int
    char_start: int
    char_end: int
    text: str
    page_from: int | None = None
    page_to: int | None = None


class ConceptHitOut(BaseModel):
    """개념 검색 결과 한 줄 — 무엇이 어느 자료 어디에 있는가."""

    id: uuid.UUID
    name: str
    definition: str | None = None
    source: str
    global_key: str | None = None
    similarity: float
    document_id: uuid.UUID
    filename: str
    topic_title: str | None = None
    evidence: list["EvidenceOut"] = Field(default_factory=list)


class ConceptOut(BaseModel):
    id: uuid.UUID
    name: str
    definition: str | None = None
    source: str
    global_key: str | None = None
    segment_seqs: list[int] = Field(default_factory=list)
    prerequisite_ids: list[uuid.UUID] = Field(default_factory=list)
    # 원문 근거. 빈 배열이면 LLM이 근거를 특정하지 못한 것이다.
    evidence: list[EvidenceOut] = Field(default_factory=list)


class TopicOut(BaseModel):
    id: uuid.UUID
    seq: int
    title: str
    page_from: int | None = None
    page_to: int | None = None
    segments: list[SegmentOut] = Field(default_factory=list)
    concepts: list[ConceptOut] = Field(default_factory=list)


class DocumentTree(BaseModel):
    """문서 전체 구조. 목차 아래에 원문 조각과 개념이 다 들어 있다."""

    document: DocumentOut
    topics: list[TopicOut] = Field(default_factory=list)
    # 목차 배정에 실패한 조각. 파싱이 성공했다면 반드시 비어 있어야 한다.
    orphan_segments: list[SegmentOut] = Field(default_factory=list)
