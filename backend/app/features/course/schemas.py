"""코스 입출력 스키마."""
from __future__ import annotations

import uuid

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
