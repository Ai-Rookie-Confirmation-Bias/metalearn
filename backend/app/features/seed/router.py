"""씨앗(Seed) — 설문·진단·커리큘럼 슬라이스."""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.seed.schemas import (
    CurriculumResponse,
    DiagnosticResultResponse,
    DiagnosticSessionResponse,
    PrerequisiteAnalysis,
    PrerequisiteAnalyzeRequest,
    SeedProfileResponse,
    SeedSlice,
    SubmitDiagnosticRequest,
    SurveyRequest,
)
from app.features.seed.service import SeedService

router = APIRouter()


@router.post("/profiles", response_model=SeedProfileResponse)
def create_profile(req: SurveyRequest, db: Session = Depends(get_db)) -> SeedProfileResponse:
    """설문 3단계 제출 → concepts_in_range 계산."""
    return SeedService(db).submit_survey(req)


@router.get("/profiles/{profile_id}", response_model=SeedProfileResponse)
def get_profile(profile_id: uuid.UUID, db: Session = Depends(get_db)) -> SeedProfileResponse:
    return SeedService(db).get_profile(profile_id)


@router.post("/profiles/{profile_id}/diagnostics", response_model=DiagnosticSessionResponse)
async def start_diagnostic(
    profile_id: uuid.UUID, db: Session = Depends(get_db)
) -> DiagnosticSessionResponse:
    """진단 문제 생성 (Solar 또는 rule-based fallback)."""
    return await SeedService(db).start_diagnostic(profile_id)


@router.post(
    "/diagnostics/{session_id}/submit",
    response_model=DiagnosticResultResponse,
)
def submit_diagnostic(
    session_id: uuid.UUID,
    req: SubmitDiagnosticRequest,
    db: Session = Depends(get_db),
) -> DiagnosticResultResponse:
    """답안 제출 → 약점(concept_id) 산출."""
    return SeedService(db).submit_diagnostic(session_id, req)


@router.get("/profiles/{profile_id}/slice", response_model=SeedSlice)
def get_seed_slice(profile_id: uuid.UUID, db: Session = Depends(get_db)) -> SeedSlice:
    """최종 Seed JSON (진단 완료 후)."""
    return SeedService(db).get_slice(profile_id)


@router.post("/prerequisites/analyze", response_model=PrerequisiteAnalysis)
async def analyze_prerequisites(
    req: PrerequisiteAnalyzeRequest, db: Session = Depends(get_db)
) -> PrerequisiteAnalysis:
    """학습 범위 기준 선행지식 AI 탐색 (Solar)."""
    return await SeedService(db).analyze_prerequisites(req)


@router.post("/profiles/{profile_id}/curriculum", response_model=CurriculumResponse)
async def generate_curriculum(
    profile_id: uuid.UUID, db: Session = Depends(get_db)
) -> CurriculumResponse:
    """진단 약점 반영 개인 맞춤 학습 로드맵 생성 (+ LLM summary)."""
    return await SeedService(db).generate_curriculum(profile_id)


@router.get("/profiles/{profile_id}/curriculum", response_model=CurriculumResponse)
def get_curriculum(profile_id: uuid.UUID, db: Session = Depends(get_db)) -> CurriculumResponse:
    return SeedService(db).get_curriculum(profile_id)
