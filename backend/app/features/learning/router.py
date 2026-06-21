"""[1.Controller] 외부 API 요청 수신."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.learning.schemas import GenerateRequest, GenerateResponse
from app.features.learning.service import LearningService

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, db: Session = Depends(get_db)) -> GenerateResponse:
    return await LearningService(db).generate(req)
