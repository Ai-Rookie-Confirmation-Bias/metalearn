"""코스 입출력 스키마."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CourseCreate(BaseModel):
    # users 테이블이 아직 없어 클라이언트가 직접 준다. auth가 들어오면 토큰에서.
    user_id: uuid.UUID
    document_ids: list[uuid.UUID] = Field(..., min_length=1)
    title: str | None = None
    # 비우면 밀도로 제안한다. {document_id: skeleton|body|reference}
    roles: dict[uuid.UUID, str] | None = None


class CourseDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: uuid.UUID
    role: str
    seq: int


class CourseTopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seq: int
    title: str
    origin: str
    plan: str
    source_topic_id: uuid.UUID | None = None
    anchor_concept_id: uuid.UUID | None = None
    note: str | None = None


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    documents: list[CourseDocumentOut] = []
    topics: list[CourseTopicOut] = []


class CourseListItem(BaseModel):
    """목록 화면용 한 줄 — topics(무거움)는 빼고 자료 구성만 싣는다."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime
    documents: list[CourseDocumentOut] = []


class PrereqOut(BaseModel):
    """이 코스를 시작하기 전에 알아야 하는 것 한 줄.

    status가 셋인 이유 — 문턱(0.49)이 표본 21개로 잰 값이라 경계 양옆은
    단정하지 않는다. 화면은 pass를 그냥 보여주고 gray는 "자료에 조금 나옴"으로
    표시하며 rejected는 숨긴다(디버그로만 본다).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject: str
    item: str
    why: str | None = None
    seq: int
    # 하위 항목 사이 순서가 강제되면 True → 보강 '단원', 아니면 한 '꼭지'.
    ordered: bool
    # pass | gray | rejected
    status: str
    # 되짚기용. 어떤 개념에 얼마나 가까워서 그렇게 판정했는가.
    similarity: float | None = None
    rejected_by: str | None = None
    # 24번 진단이 채운다: known | heard | unknown
    known: str | None = None


class BodyRefOut(BaseModel):
    """18단계가 붙인 것 — 이 개념을 **다른 자료**가 설명하는 곳.

    뼈대(PPT)에는 표제어만 있고 본문(교재)에 설명이 세 쪽 있는 상황을 잇는다.
    `kind`가 related면 상위·하위 개념이라 설명이 조금 넓거나 좁을 수 있다.
    """

    concept_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    name: str
    definition: str | None = None
    similarity: float
    kind: str          # same | related
    verified_by: str   # embed | llm
    # 그 개념이 설명되는 원문 조각. 화면이 이걸 그대로 본문으로 쓴다.
    segments: list["BodySegmentOut"] = Field(default_factory=list)


class BodySegmentOut(BaseModel):
    id: uuid.UUID
    seq: int
    heading: str | None = None
    content: str
    page_from: int | None = None
    page_to: int | None = None


class CourseConceptOut(BaseModel):
    """뼈대 자료의 개념 하나 + 본문 자료에서 끌어온 설명."""

    id: uuid.UUID
    name: str
    definition: str | None = None
    source: str
    global_key: str | None = None
    document_id: uuid.UUID
    filename: str
    segment_seqs: list[int] = Field(default_factory=list)
    prerequisite_ids: list[uuid.UUID] = Field(default_factory=list)
    # 뼈대 자료 안에서의 근거 위치(조각/문장/글자 offset).
    evidence: list[dict] = Field(default_factory=list)
    # 다른 자료가 이 개념을 설명한다면 여기 붙는다. 유사도 높은 순.
    body: list[BodyRefOut] = Field(default_factory=list)


class CourseTopicNode(BaseModel):
    id: uuid.UUID
    seq: int
    title: str
    origin: str
    plan: str
    # 복사 원본(doc_topics). 보강 단원은 없으므로 NULL.
    source_topic_id: uuid.UUID | None = None
    concepts: list[CourseConceptOut] = Field(default_factory=list)
    segments: list[BodySegmentOut] = Field(default_factory=list)


class CourseTree(BaseModel):
    """코스 전체 — **뼈대 목차 순서로 가되 설명은 본문 자료에서.**

    문서 트리(GET /parsing/documents/{id}/tree)와 다른 점이 이것이다.
    문서 트리는 책 한 권 안에서만 보고, 여기는 코스에 묶인 자료 전부를 본다.
    """

    course_id: uuid.UUID
    title: str
    # 목차를 제공한 자료. 여기 목차 순서가 곧 학습 순서다.
    skeleton_document_id: uuid.UUID | None = None
    # 설명을 대는 자료들.
    body_document_ids: list[uuid.UUID] = Field(default_factory=list)
    topics: list[CourseTopicNode] = Field(default_factory=list)
    # 몇 개 개념에 본문이 붙었나. 자료 조합이 쓸모 있는지 한눈에 보는 값.
    linked_concepts: int = 0
    total_concepts: int = 0


class GapOut(BaseModel):
    """끊긴 고리 하나 — 책이 필요하다고 하는데 설명이 없는 개념."""

    concept_id: uuid.UUID
    name: str
    global_key: str | None = None
    definition: str | None = None
    # 이 개념을 선수로 부르는 개념 수 / 그 개념들이 속한 단원 수.
    # 단원 수가 많을수록 "여러 군데서 필요한 기초" → 보강 단원 값어치가 크다.
    refs: int
    topics: int
