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
    """(하위호환) 트리+슬러그+외부근거 + enrollment/mastery 한 번에."""
    return await SeedService(db).build(course_id, purpose=purpose)


@router.post("/{course_id}/tree")
async def build_tree(course_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    """1단계: 커리큘럼 트리 + 슬러그 + external_refs (진단 무관)."""
    return await SeedService(db).build_tree(course_id)


@router.post("/{course_id}/placement")
async def finalize_placement(
    course_id: uuid.UUID, purpose: str = "exam", db: Session = Depends(get_db)
) -> dict:
    """2단계: 진단 완료 후 enrollment 확정 + mastery 시드 JSON."""
    return await SeedService(db).finalize_placement(course_id, purpose=purpose)
