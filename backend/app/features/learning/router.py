"""[1.Controller] 외부 API 요청 수신."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.learning.schemas import (
    CurriculumRequest,
    CurriculumResponse,
    GenerateRequest,
    GenerateResponse,
)
from app.features.learning.service import LearningService

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, db: Session = Depends(get_db)) -> GenerateResponse:
    return await LearningService(db).generate(req)


@router.post("/curriculum", response_model=CurriculumResponse)
async def curriculum(
    req: CurriculumRequest, db: Session = Depends(get_db)
) -> CurriculumResponse:
    """JIT 적응형 커리큘럼 생성 (챕터=개념 진입 시 트리거)."""
    return await LearningService(db).generate_curriculum(req)
