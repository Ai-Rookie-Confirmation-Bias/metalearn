"""[2.DTO] 복습 계약 (docs/API.md 복습 섹션).

복습 = concept_mastery.next_due_at 도래 개념을 다시 인출. 스케줄은 SM-2(sm2.py)가
record_attempt(kind=review) 시점에 갱신한다. 여기선 조회 응답 모양만 정의.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.features.learning.schemas import BlockEnvelope


def _to_camel(s: str) -> str:
    head, *rest = s.split("_")
    return head + "".join(w.capitalize() for w in rest)


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


class ReviewDueItem(_CamelModel):
    """복습 도래 개념 1건 + 다시 답할 블록(정답 스트립 봉투)."""

    concept_id: str
    concept_name: str
    section_id: str | None = None
    next_due_at: str | None = None
    block: BlockEnvelope | None = None


class ReviewDueResponse(_CamelModel):
    """GET /review/due → 도래 개념 목록."""

    due_count: int = 0
    items: list[ReviewDueItem] = Field(default_factory=list)


class ReviewScheduleItem(_CamelModel):
    concept_id: str
    concept_name: str
    next_due_at: str | None = None
    strength: float = 0.0
    status: str = "learning"


class ReviewScheduleResponse(_CamelModel):
    """GET /review/schedule → 다가오는 복습 캘린더."""

    items: list[ReviewScheduleItem] = Field(default_factory=list)
