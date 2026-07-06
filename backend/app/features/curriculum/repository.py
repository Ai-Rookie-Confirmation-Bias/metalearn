"""[4.Repository] 커리큘럼 트리 조회 — 코스의 챕터/절 + 학습자 상태 일괄 로드."""
from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.features.curriculum.models import Chapter, Section
from app.features.learning.models import Attempt, ConceptMastery, SectionProgress
from app.features.seed.models import Concept, Course


def get_course(db: Session, course_id: uuid.UUID) -> Course | None:
    return db.get(Course, course_id)


def get_course_chapters(db: Session, course_id: uuid.UUID) -> list[Chapter]:
    stmt = (
        select(Chapter)
        .where(Chapter.course_id == course_id)
        .order_by(Chapter.order_index)
    )
    return list(db.scalars(stmt))


def get_sections_by_chapters(
    db: Session, chapter_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[Section]]:
    """chapter_id → 정렬된 절 리스트(N+1 방지 일괄 조회)."""
    if not chapter_ids:
        return {}
    stmt = (
        select(Section)
        .where(Section.chapter_id.in_(chapter_ids))
        .order_by(Section.order_index)
    )
    out: dict[uuid.UUID, list[Section]] = {cid: [] for cid in chapter_ids}
    for s in db.scalars(stmt):
        out.setdefault(s.chapter_id, []).append(s)
    return out


def get_progress_map(
    db: Session, *, user_id: uuid.UUID, section_ids: list[uuid.UUID]
) -> dict[uuid.UUID, SectionProgress]:
    if not section_ids:
        return {}
    stmt = select(SectionProgress).where(
        SectionProgress.user_id == user_id,
        SectionProgress.section_id.in_(section_ids),
    )
    return {p.section_id: p for p in db.scalars(stmt)}


def get_mastery_map(
    db: Session, *, user_id: uuid.UUID, concept_ids: list[uuid.UUID]
) -> dict[uuid.UUID, ConceptMastery]:
    if not concept_ids:
        return {}
    stmt = select(ConceptMastery).where(
        ConceptMastery.user_id == user_id,
        ConceptMastery.concept_id.in_(concept_ids),
    )
    return {m.concept_id: m for m in db.scalars(stmt)}


# ── 책장 목록 집계 (GET /courses) ────────────────────────────────────────────
def list_user_courses(db: Session, user_id: uuid.UUID) -> list[Course]:
    stmt = (
        select(Course)
        .where(Course.user_id == user_id)
        .order_by(Course.created_at.desc())
    )
    return list(db.scalars(stmt))


def count_sections_by_course(
    db: Session, course_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    if not course_ids:
        return {}
    stmt = (
        select(Chapter.course_id, func.count(Section.id))
        .join(Section, Section.chapter_id == Chapter.id)
        .where(Chapter.course_id.in_(course_ids))
        .group_by(Chapter.course_id)
    )
    return {cid: n for cid, n in db.execute(stmt)}


def count_completed_sections_by_course(
    db: Session, *, user_id: uuid.UUID, course_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    if not course_ids:
        return {}
    stmt = (
        select(Chapter.course_id, func.count(SectionProgress.section_id))
        .select_from(SectionProgress)
        .join(Section, Section.id == SectionProgress.section_id)
        .join(Chapter, Chapter.id == Section.chapter_id)
        .where(
            SectionProgress.user_id == user_id,
            SectionProgress.status == "completed",
            Chapter.course_id.in_(course_ids),
        )
        .group_by(Chapter.course_id)
    )
    return {cid: n for cid, n in db.execute(stmt)}


def count_concepts_by_course(
    db: Session, course_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    if not course_ids:
        return {}
    stmt = (
        select(Concept.course_id, func.count(Concept.id))
        .where(Concept.course_id.in_(course_ids))
        .group_by(Concept.course_id)
    )
    return {cid: n for cid, n in db.execute(stmt)}


def last_activity_by_course(
    db: Session, *, user_id: uuid.UUID, course_ids: list[uuid.UUID]
) -> dict[uuid.UUID, datetime]:
    """코스별 MAX(attempts.created_at) — 저장 아닌 계산값. attempts→concepts로 조인."""
    if not course_ids:
        return {}
    stmt = (
        select(Concept.course_id, func.max(Attempt.created_at))
        .select_from(Attempt)
        .join(Concept, Concept.id == Attempt.concept_id)
        .where(Attempt.user_id == user_id, Concept.course_id.in_(course_ids))
        .group_by(Concept.course_id)
    )
    return {cid: ts for cid, ts in db.execute(stmt)}


# ── 개념별 숙련도 (GET /courses/:id/mastery) ─────────────────────────────────
def get_concepts_of_course(db: Session, course_id: uuid.UUID) -> list[Concept]:
    stmt = (
        select(Concept)
        .where(Concept.course_id == course_id)
        .order_by(Concept.depth_level, Concept.name)
    )
    return list(db.scalars(stmt))
