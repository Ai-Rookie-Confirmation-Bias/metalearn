"""[1.Controller] 복습 API (docs/API.md 복습 섹션). app/api.py에서 '/review' prefix로 등록.

  GET  /review/due?courseId=      — 도래 개념 + 다시 답할 블록
  POST /review/answer             — 복습 응답 → 서버 채점 + SM-2 간격 갱신
  GET  /review/schedule?courseId= — 복습 캘린더
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.features.learning import service as learning_service
from app.features.learning.schemas import AttemptRequest, AttemptResponse
from app.features.review import service
from app.features.review.schemas import ReviewDueResponse, ReviewScheduleResponse

router = APIRouter()


@router.get("/due", response_model=ReviewDueResponse)
def review_due(
    course_id: uuid.UUID | None = Query(None, alias="courseId"),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ReviewDueResponse:
    return service.list_due(db, user_id=user_id, course_id=course_id)


@router.get("/schedule", response_model=ReviewScheduleResponse)
def review_schedule(
    course_id: uuid.UUID | None = Query(None, alias="courseId"),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ReviewScheduleResponse:
    return service.list_schedule(db, user_id=user_id, course_id=course_id)


@router.post("/answer", response_model=AttemptResponse)
async def review_answer(
    body: AttemptRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> AttemptResponse:
    """복습 응답 = kind=review로 고정한 attempt. 채점·SM-2 갱신은 record_attempt가 처리."""
    body.kind = "review"
    return await learning_service.record_attempt(db, user_id=user_id, req=body)
