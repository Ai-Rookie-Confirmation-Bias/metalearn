"""[4.Repository] 커리큘럼 트리 조회 — 코스의 챕터/절 + 학습자 상태 일괄 로드."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.curriculum.models import Chapter, Section
from app.features.learning.models import ConceptMastery, SectionProgress
from app.features.seed.models import Course


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
