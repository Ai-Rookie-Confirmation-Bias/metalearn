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
    # 잠금(서버 계산): 순차 진행 — 완료된 절 + 첫 미완료까지 열림, 그 뒤는 잠김
    locked: bool = False


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


# ── 책장 목록 (GET /courses, API.md line 27) ─────────────────────────────────
class CourseListItem(_CamelModel):
    """책장 카드 1개 — 진행률 + 마지막 활동(계산값)."""

    course_id: str
    title: str
    category: str | None = None
    concept_count: int = 0
    total_sections: int = 0
    completed_sections: int = 0
    progress: float = 0.0  # 0~1 = completed/total
    # 진단 상태(ISSUE-018) — enrollments.diag_status. 섹션 수 프록시가 아니라
    # 서버 진실. not_started | in_progress | completed
    diag_status: str = "not_started"
    # MAX(attempts.created_at) — 저장 아닌 계산값
    last_activity_at: str | None = None


class CourseListResponse(_CamelModel):
    courses: list[CourseListItem] = Field(default_factory=list)


# ── 개념별 숙련도 (GET /courses/:id/mastery, API.md line 49) ──────────────────
class ConceptMasteryItem(_CamelModel):
    concept_id: str
    key: str | None = None
    name: str
    depth_level: int | None = None
    status: str = "locked"  # locked | todo | learning | mastered
    strength: float = 0.0
    explanation_score: float = 0.0
    confidence: str | None = None
    next_due_at: str | None = None


class MasteryResponse(_CamelModel):
    """GET /courses/:id/mastery → 메타인지 분석용 개념별 숙련도 + 요약."""

    course_id: str
    mastered: int = 0
    learning: int = 0
    todo: int = 0
    locked: int = 0
    concepts: list[ConceptMasteryItem] = Field(default_factory=list)
