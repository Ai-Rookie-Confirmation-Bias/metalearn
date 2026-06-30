"""[1.Controller] 정밀 진단(BKT) API."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.diagnostic.schemas import (
    AnswerRequest,
    AnswerResult,
    SessionState,
    StartRequest,
)
from app.features.diagnostic.service import DiagnosticService

router = APIRouter()


@router.post("/start", response_model=SessionState, status_code=201)
async def start(req: StartRequest, db: Session = Depends(get_db)) -> SessionState:
    return await DiagnosticService(db).start(req.material_id)


@router.get("/{session_id}", response_model=SessionState)
async def get_state(session_id: int, db: Session = Depends(get_db)) -> SessionState:
    return await DiagnosticService(db).get_state(session_id)


@router.post(
    "/{session_id}/questions/{question_id}/answer", response_model=AnswerResult
)
async def answer(
    session_id: int,
    question_id: int,
    req: AnswerRequest,
    db: Session = Depends(get_db),
) -> AnswerResult:
    return await DiagnosticService(db).answer(
        session_id,
        question_id,
        selected_index=req.selected_index,
        answer_text=req.answer_text,
    )
