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
    CourseTreeResponse,
    SectionNode,
)

router = APIRouter()


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

    all_sections = [s for lst in sections_by_chapter.values() for s in lst]
    progress = repo.get_progress_map(
        db, user_id=user_id, section_ids=[s.id for s in all_sections]
    )
    mastery = repo.get_mastery_map(
        db,
        user_id=user_id,
        concept_ids=[s.concept_id for s in all_sections if s.concept_id],
    )

    chapter_nodes: list[ChapterNode] = []
    for ch in chapters:
        section_nodes: list[SectionNode] = []
        for s in sections_by_chapter.get(ch.id, []):
            p = progress.get(s.id)
            m = mastery.get(s.concept_id) if s.concept_id else None
            section_nodes.append(
                SectionNode(
                    id=str(s.id),
                    title=s.title,
                    order_index=s.order_index,
                    concept_id=str(s.concept_id) if s.concept_id else None,
                    progress_status=p.status if p else "not_started",
                    variant_served=p.variant_served if p else None,
                    mastery_status=m.status if m else None,
                    strength=m.strength if m else None,
                )
            )
        chapter_nodes.append(
            ChapterNode(
                id=str(ch.id),
                title=ch.title,
                order_index=ch.order_index,
                origin=ch.origin,
                gen_status=ch.gen_status,
                sections=section_nodes,
            )
        )

    return CourseTreeResponse(
        course_id=str(course.id), title=course.title, chapters=chapter_nodes
    )
