"""[3.Service] 복습 유스케이스 — 도래 개념 조회 + 다시 답할 블록 봉투.

스케줄 갱신(SM-2)은 record_attempt(kind=review)가 담당. 여기선 조회만.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.features.learning import repository as repo
from app.features.learning.serializer import to_envelope
from app.features.review.schemas import (
    ReviewDueItem,
    ReviewDueResponse,
    ReviewScheduleItem,
    ReviewScheduleResponse,
)


def list_due(
    db: Session, *, user_id: uuid.UUID, course_id: uuid.UUID | None
) -> ReviewDueResponse:
    """복습 도래 개념 + 각 개념의 다시 답할 블록(정답 스트립 봉투)."""
    now = datetime.now(timezone.utc)
    rows = repo.get_due_masteries(db, user_id=user_id, course_id=course_id, now=now)

    items: list[ReviewDueItem] = []
    for mastery, concept in rows:
        section = repo.find_section_by_concept(
            db, course_id=concept.course_id, concept_id=concept.id
        )
        env = None
        if section is not None:
            block = repo.get_review_block(db, section.id)
            if block is not None:
                refs = repo.get_external_refs_by_ids(db, block.external_ref_ids or [])
                env = to_envelope(block, external_refs=refs)
                env.kind = "review"  # 프론트가 attempts에 kind=review로 보내게
        items.append(
            ReviewDueItem(
                concept_id=str(concept.id),
                concept_name=concept.name,
                section_id=str(section.id) if section else None,
                next_due_at=(
                    mastery.next_due_at.isoformat() if mastery.next_due_at else None
                ),
                block=env,
            )
        )
    return ReviewDueResponse(due_count=len(items), items=items)


def list_schedule(
    db: Session, *, user_id: uuid.UUID, course_id: uuid.UUID | None
) -> ReviewScheduleResponse:
    """다가오는 복습 캘린더(개념별 next_due_at)."""
    rows = repo.get_schedule_masteries(db, user_id=user_id, course_id=course_id)
    items = [
        ReviewScheduleItem(
            concept_id=str(concept.id),
            concept_name=concept.name,
            next_due_at=(
                mastery.next_due_at.isoformat() if mastery.next_due_at else None
            ),
            strength=mastery.strength,
            status=mastery.status,
        )
        for mastery, concept in rows
    ]
    return ReviewScheduleResponse(items=items)
