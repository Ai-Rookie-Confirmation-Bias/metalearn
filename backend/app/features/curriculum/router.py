"""[1.Controller] 커리큘럼 API — GET /courses/:id (챕터/절 트리 + 학습자 진행).

docs/API.md 경로와 일치하도록 prefix 없이 등록한다(app/api.py 참고).
커리큘럼 '생성'(위상정렬 → chapters/sections INSERT)은 씨앗(seed) 완료 후
연결한다 — service.build_curriculum은 순수 계층으로 이미 준비됨.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.features.curriculum import repository as repo
from app.features.curriculum.schemas import (
    ChapterNode,
    ConceptMasteryItem,
    CourseListItem,
    CourseListResponse,
    CourseTreeResponse,
    MasteryResponse,
    SectionNode,
)

router = APIRouter()


@router.get("/courses", response_model=CourseListResponse)
def list_courses(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> CourseListResponse:
    """내 책장 — 코스별 진행률 + 마지막 활동(=MAX(attempts.created_at), 계산값)."""
    courses = repo.list_user_courses(db, user_id)
    ids = [c.id for c in courses]
    totals = repo.count_sections_by_course(db, ids)
    done = repo.count_completed_sections_by_course(db, user_id=user_id, course_ids=ids)
    concepts = repo.count_concepts_by_course(db, ids)
    activity = repo.last_activity_by_course(db, user_id=user_id, course_ids=ids)
    diag = repo.diag_status_by_course(db, user_id=user_id, course_ids=ids)

    items: list[CourseListItem] = []
    for c in courses:
        total = totals.get(c.id, 0)
        comp = done.get(c.id, 0)
        la = activity.get(c.id)
        items.append(
            CourseListItem(
                course_id=str(c.id),
                title=c.title,
                category=c.category,
                concept_count=concepts.get(c.id, 0),
                total_sections=total,
                completed_sections=comp,
                progress=round(comp / total, 4) if total else 0.0,
                diag_status=diag.get(c.id, "not_started"),
                last_activity_at=la.isoformat() if la else None,
            )
        )
    return CourseListResponse(courses=items)


@router.get("/courses/{course_id}/mastery", response_model=MasteryResponse)
def get_course_mastery(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> MasteryResponse:
    """개념별 숙련도(메타인지 분석). 개념 그래프 전체 + 학습자 상태 + 상태별 요약."""
    course = repo.get_course(db, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="course not found")

    concepts = repo.get_concepts_of_course(db, course_id)
    mmap = repo.get_mastery_map(
        db, user_id=user_id, concept_ids=[c.id for c in concepts]
    )
    counts = {"mastered": 0, "learning": 0, "todo": 0, "locked": 0}
    items: list[ConceptMasteryItem] = []
    for c in concepts:
        m = mmap.get(c.id)
        status = m.status if m else "locked"
        counts[status] = counts.get(status, 0) + 1
        items.append(
            ConceptMasteryItem(
                concept_id=str(c.id),
                key=c.key,
                name=c.name,
                depth_level=c.depth_level,
                status=status,
                strength=m.strength if m else 0.0,
                explanation_score=m.explanation_score if m else 0.0,
                confidence=m.confidence if m else None,
                next_due_at=(
                    m.next_due_at.isoformat() if m and m.next_due_at else None
                ),
            )
        )
    return MasteryResponse(course_id=str(course_id), concepts=items, **counts)


@router.get("/courses/{course_id}", response_model=CourseTreeResponse)
def get_course_tree(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> CourseTreeResponse:
    course = repo.get_course(db, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="course not found")

    chapters = repo.get_course_chapters(db, course_id)
    sections_by_chapter = repo.get_sections_by_chapters(db, [c.id for c in chapters])

    # 선행 삽입 이유(변화 가시성 §4) — prereq 챕터가 왜 생겼는지 서버가 말한다
    prereq_ids = [c.id for c in chapters if c.origin == "prereq"]
    triggers = repo.prereq_triggers_by_chapter(
        db, user_id=user_id, chapter_ids=prereq_ids
    )

    all_sections = [s for lst in sections_by_chapter.values() for s in lst]
    progress = repo.get_progress_map(
        db, user_id=user_id, section_ids=[s.id for s in all_sections]
    )
    mastery = repo.get_mastery_map(
        db,
        user_id=user_id,
        concept_ids=[s.concept_id for s in all_sections if s.concept_id],
    )

    # 잠금 = 순차 진행(서버 계산): 이미 완료했거나 이전 절이 전부 완료면 열림, 아니면 잠금.
    # (완료된 절은 순서와 무관하게 항상 열림 — 되돌아보기 허용). 커리큘럼 순서로 스캔.
    all_prior_completed = True

    chapter_nodes: list[ChapterNode] = []
    for ch in chapters:
        section_nodes: list[SectionNode] = []
        for s in sections_by_chapter.get(ch.id, []):
            p = progress.get(s.id)
            m = mastery.get(s.concept_id) if s.concept_id else None
            status = p.status if p else "not_started"
            completed = status == "completed"
            locked = not (completed or all_prior_completed)
            all_prior_completed = all_prior_completed and completed
            section_nodes.append(
                SectionNode(
                    id=str(s.id),
                    title=s.title,
                    order_index=s.order_index,
                    concept_id=str(s.concept_id) if s.concept_id else None,
                    progress_status=status,
                    variant_served=p.variant_served if p else None,
                    mastery_status=m.status if m else None,
                    strength=m.strength if m else None,
                    locked=locked,
                )
            )
        trigger = triggers.get(ch.id) if ch.origin == "prereq" else None
        reason = (
            f"'{trigger}' 문제를 틀렸을 때 이 개념이 기반이라고 판단해서, "
            "먼저 다지도록 앞에 끼워 넣었어요"
            if trigger
            else (
                "본편을 배우기 전에 필요한 선수 개념이라 앞에 끼워 넣었어요"
                if ch.origin == "prereq"
                else None
            )
        )
        chapter_nodes.append(
            ChapterNode(
                id=str(ch.id),
                title=ch.title,
                order_index=ch.order_index,
                origin=ch.origin,
                gen_status=ch.gen_status,
                reason=reason,
                sections=section_nodes,
            )
        )

    return CourseTreeResponse(
        course_id=str(course.id), title=course.title, chapters=chapter_nodes
    )
