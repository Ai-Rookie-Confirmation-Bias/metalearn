"""[1.Controller] 학습·튜터 세션 API."""
import uuid
from typing import Union

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.learning.schemas import (
    CompleteSessionResponse,
    GenerateRequest,
    GenerateResponse,
    HintResponse,
    RespondCorrectResponse,
    RespondIncorrectResponse,
    RespondRequest,
    StartPrerequisiteResponse,
    StartSessionRequest,
    StartSessionResponse,
)
from app.features.learning.service import LearningService

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, db: Session = Depends(get_db)) -> GenerateResponse:
    return await LearningService(db).generate(req)


@router.post("/sessions", response_model=StartSessionResponse)
async def start_session(
    req: StartSessionRequest, db: Session = Depends(get_db)
) -> StartSessionResponse:
    """커리큘럼 단원 기반 튜터 세션 시작 + 역질문 생성."""
    return await LearningService(db).start_session(req)


@router.post("/sessions/{session_id}/prerequisite", response_model=StartPrerequisiteResponse)
async def start_prerequisite_session(
    session_id: uuid.UUID, db: Session = Depends(get_db)
) -> StartPrerequisiteResponse:
    """answer_reveal 이후 호출 — 선수 개념 세션 생성.
    프론트는 이 세션을 완료 후 return_to_session_id로 복귀."""
    return await LearningService(db).start_prerequisite_session(session_id)


@router.post(
    "/sessions/{session_id}/respond",
    response_model=Union[RespondCorrectResponse, RespondIncorrectResponse],
)
async def respond_to_session(
    session_id: uuid.UUID,
    req: RespondRequest,
    db: Session = Depends(get_db),
) -> RespondCorrectResponse | RespondIncorrectResponse:
    """학습자 답변 제출 → 정오 판단 (틀리면 hint_1 제공)."""
    return await LearningService(db).respond(session_id, req.user_response)


@router.get("/sessions/{session_id}/hint", response_model=HintResponse)
async def get_hint(
    session_id: uuid.UUID, db: Session = Depends(get_db)
) -> HintResponse:
    """hint_2 또는 answer_reveal 단계 제공."""
    return await LearningService(db).get_hint(session_id)


@router.post("/sessions/{session_id}/complete", response_model=CompleteSessionResponse)
def complete_session(
    session_id: uuid.UUID, db: Session = Depends(get_db)
) -> CompleteSessionResponse:
    """세션 완료 후 약점 목록 갱신.
    prerequisite 세션이면 return_to_session_id에 부모 세션 ID 포함."""
    return LearningService(db).complete_session(session_id)
