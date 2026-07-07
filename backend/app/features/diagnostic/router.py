"""[1.Controller] 진단 API — 배치고사(placement) + 정밀 진단(BKT, 구형). (병합 2단계: UUID)"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.diagnostic.placement import PlacementService
from app.features.diagnostic.schemas import (
    AnswerRequest,
    AnswerResult,
    PlacementState,
    SessionState,
    StartRequest,
)
from app.features.diagnostic.service import DiagnosticService

router = APIRouter()


# ── 배치고사 (ISSUE-015 — 짧은 진단, 바닥 찾기. 라우트 shadowing 방지 위해 먼저) ──


@router.post("/placement/start", response_model=PlacementState, status_code=201)
async def placement_start(
    req: StartRequest, db: Session = Depends(get_db)
) -> PlacementState:
    """배치고사 시작 — 문항 1개씩 서빙, 5~12문항에 floor 확정."""
    return await PlacementService(db).start(req.course_id)


@router.post(
    "/placement/{session_id}/questions/{question_id}/answer",
    response_model=PlacementState,
)
async def placement_answer(
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    req: AnswerRequest,
    db: Session = Depends(get_db),
) -> PlacementState:
    """응답 → 다음 문항 또는 종료(floor/ceiling + 시드)."""
    return await PlacementService(db).answer(
        session_id,
        question_id,
        selected_index=req.selected_index,
        answer_text=req.answer_text,
    )


# ── 전수/스코핑 진단 (구형 — lab 호환용 유지) ──────────────────


@router.post("/start", response_model=SessionState, status_code=201)
async def start(req: StartRequest, db: Session = Depends(get_db)) -> SessionState:
    return await DiagnosticService(db).start(req.course_id)


@router.get("/{session_id}", response_model=SessionState)
async def get_state(
    session_id: uuid.UUID, db: Session = Depends(get_db)
) -> SessionState:
    return await DiagnosticService(db).get_state(session_id)


@router.post(
    "/{session_id}/questions/{question_id}/answer", response_model=AnswerResult
)
async def answer(
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    req: AnswerRequest,
    db: Session = Depends(get_db),
) -> AnswerResult:
    return await DiagnosticService(db).answer(
        session_id,
        question_id,
        selected_index=req.selected_index,
        answer_text=req.answer_text,
    )
