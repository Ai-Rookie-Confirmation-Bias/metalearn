"""[2.DTO] 커리큘럼 트리 계약 — GET /courses/:id (docs/API.md 자료/코스 섹션).

프론트 커리큘럼 화면이 그리는 챕터/절 트리. 절에는 학습자 진행 상태를 얹는다
(진행도 = 서버 진실 → React Query 미러, 기획서 §8).
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(s: str) -> str:
    head, *rest = s.split("_")
    return head + "".join(w.capitalize() for w in rest)


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


class SectionNode(_CamelModel):
    id: str
    title: str
    order_index: int
    concept_id: str | None = None
    # 학습자 상태(없으면 not_started/None)
    progress_status: str = "not_started"  # not_started | in_progress | completed
    variant_served: str | None = None
    mastery_status: str | None = None  # locked | todo | learning | mastered
    strength: float | None = None


class ChapterNode(_CamelModel):
    id: str
    title: str
    order_index: int
    origin: str  # book | prereq
    gen_status: str  # pending | generating | ready | failed
    sections: list[SectionNode] = Field(default_factory=list)


class CourseTreeResponse(_CamelModel):
    """GET /courses/:id → 챕터/절 트리 + 학습자 진행."""

    course_id: str
    title: str
    chapters: list[ChapterNode] = Field(default_factory=list)
