"""[1.Controller] 씨앗 조립 API — 계약 산출물 생성. (병합 2단계: parsing 복원 + UUID)"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.seed.service import SeedService

router = APIRouter()


@router.post("/{course_id}/build")
async def build_seed(
    course_id: uuid.UUID, purpose: str = "exam", db: Session = Depends(get_db)
) -> dict:
    """커리큘럼 트리 + 슬러그 + enrollment 확정 + 시드 JSON 반환."""
    return await SeedService(db).build(course_id, purpose=purpose)
