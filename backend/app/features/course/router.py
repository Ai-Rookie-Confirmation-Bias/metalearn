"""코스 라우터.

  POST /courses            자료 묶어 수업 만들기 (역할 자동 제안 + 목차 복사)
  GET  /courses/{id}       자료·역할·목차
  GET  /courses/{id}/gaps  끊긴 고리 (외부 조달 후보)
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.course.schemas import CourseCreate, CourseOut, GapOut
from app.features.course.service import CourseService

router = APIRouter()


@router.post("", response_model=CourseOut, status_code=201)
def create_course(
    body: CourseCreate, db: Session = Depends(get_db)
) -> CourseOut:
    service = CourseService(db)
    try:
        course = service.create(
            user_id=body.user_id,
            document_ids=body.document_ids,
            title=body.title,
            roles=body.roles,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return CourseOut.model_validate(course)


@router.get("/{course_id}", response_model=CourseOut)
def get_course(course_id: uuid.UUID, db: Session = Depends(get_db)) -> CourseOut:
    try:
        return CourseOut.model_validate(CourseService(db).get(course_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{course_id}/gaps", response_model=list[GapOut])
def get_gaps(course_id: uuid.UUID, db: Session = Depends(get_db)) -> list[GapOut]:
    try:
        return [GapOut(**g) for g in CourseService(db).gaps(course_id)]
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
