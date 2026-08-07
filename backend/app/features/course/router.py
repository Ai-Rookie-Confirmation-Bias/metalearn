"""코스 라우터.

  POST /courses            자료 묶어 수업 만들기 (역할 자동 제안 + 목차 복사)
  GET  /courses/{id}       자료·역할·목차
  GET  /courses/{id}/gaps  끊긴 고리 (외부 조달 후보)
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.course.schemas import (
    CourseCreate,
    CourseListItem,
    CourseOut,
    CourseTree,
    GapOut,
    PrereqOut,
)
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


@router.get("", response_model=list[CourseListItem])
def list_courses(db: Session = Depends(get_db)) -> list[CourseListItem]:
    """코스 목록, 최신 생성 순 — 문제집 과목 선택 화면이 쓴다 (INTEGRATION §4 선행 과제)."""
    return [
        CourseListItem.model_validate(c) for c in CourseService(db).list_courses()
    ]


@router.get("/{course_id}", response_model=CourseOut)
def get_course(course_id: uuid.UUID, db: Session = Depends(get_db)) -> CourseOut:
    try:
        return CourseOut.model_validate(CourseService(db).get(course_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{course_id}/tree", response_model=CourseTree)
async def get_course_tree(
    course_id: uuid.UUID,
    force_link: bool = False,
    db: Session = Depends(get_db),
) -> CourseTree:
    """**뼈대 목차 순서 + 본문 자료의 설명.**

    PPT에는 표제어만 있고 교재에 설명이 세 쪽 있을 때, 각 개념에 그 설명이
    `body`로 붙어 나온다. 개념 연결은 첫 호출에서 계산해 문서쌍 단위로 저장
    하므로 같은 두 책을 쓰는 다음 코스는 계산이 없다.

    문서 트리(GET /parsing/documents/{id}/tree)는 책 한 권 안만 본다.
    """
    try:
        return await CourseService(db).tree(course_id, force_link=force_link)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{course_id}/prereqs", response_model=list[PrereqOut])
async def get_prereqs(
    course_id: uuid.UUID,
    refresh: bool = False,
    status: str | None = Query(None, description="pass|gray|rejected 로 거르기"),
    db: Session = Depends(get_db),
) -> list[PrereqOut]:
    """이 코스를 시작하기 전에 알아야 하는 것.

    첫 호출에서 계산하고 저장한다(임베딩 1회). 이후는 조회뿐이다.
    자료 구성을 바꿨으면 refresh=true.

    기각된 항목도 돌려주는 게 기본이다 — 왜 빠졌는지 되짚을 수 있어야 문턱을
    옮길 근거가 생긴다. 화면에는 status=pass,gray만 쓴다.
    """
    try:
        rows = await CourseService(db).prereqs(course_id, refresh=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if status:
        wanted = {s.strip() for s in status.split(",") if s.strip()}
        rows = [r for r in rows if r.status in wanted]
    return [PrereqOut.model_validate(r) for r in rows]


@router.get("/{course_id}/gaps", response_model=list[GapOut])
def get_gaps(course_id: uuid.UUID, db: Session = Depends(get_db)) -> list[GapOut]:
    try:
        return [GapOut(**g) for g in CourseService(db).gaps(course_id)]
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
