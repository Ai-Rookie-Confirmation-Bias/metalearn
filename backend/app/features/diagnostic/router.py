"""[1.Controller] 진단 API — 온보딩(실사용) + 배치고사·전수 진단(구형, lab 호환).

진단 재설계: 실사용 경로는 /onboarding/* (성향 프로파일링 + 기반지식 체크).
/placement/*(floor 찾기)와 /start(전수)는 lab 호환용으로 동결 유지.
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.diagnostic.onboarding import OnboardingService
from app.features.diagnostic.placement import PlacementService
from app.features.diagnostic.schemas import (
    AnswerRequest,
    AnswerResult,
    OnboardingAnswerRequest,
    OnboardingState,
    PlacementState,
    SessionState,
    StartRequest,
)
from app.features.diagnostic.service import DiagnosticService

router = APIRouter()


# ── 온보딩 (진단 재설계 — 성향 + 기반지식. 실사용 경로) ─────────────


@router.post("/onboarding/start", response_model=OnboardingState, status_code=201)
async def onboarding_start(
    req: StartRequest, db: Session = Depends(get_db)
) -> OnboardingState:
    """온보딩 시작 — 성향 문항(즉답) → 스타일 프로브 → 기반지식 체크."""
    return await OnboardingService(db).start(req.course_id)


@router.post("/onboarding/{session_id}/answer", response_model=OnboardingState)
async def onboarding_answer(
    session_id: uuid.UUID,
    req: OnboardingAnswerRequest,
    db: Session = Depends(get_db),
) -> OnboardingState:
    """단계별 응답 → 다음 단계 또는 종료(프로필 카드 + 시딩 결과)."""
    return await OnboardingService(db).answer(
        session_id,
        choice_index=req.choice_index,
        question_id=req.question_id,
        selected_index=req.selected_index,
        answer_text=req.answer_text,
    )


# ── 배치고사 (ISSUE-015 — 구형, lab 호환 동결. 라우트 shadowing 방지 위해 먼저) ──


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
