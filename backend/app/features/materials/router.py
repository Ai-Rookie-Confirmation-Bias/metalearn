"""학습 자료(RAG) 라우터 — PDF 업로드·skeleton."""
import uuid

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.materials.schemas import DocumentResponse, DocumentSkeleton
from app.features.materials.service import MaterialsService

router = APIRouter()


@router.post("/documents", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile,
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """PDF 업로드 → 페이지 청킹 → skeleton 생성 (API 키 없으면 mock embed)."""
    return await MaterialsService(db).upload_and_parse(file)


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db)) -> DocumentResponse:
    return MaterialsService(db).get_document(document_id)


@router.get("/documents/{document_id}/skeleton", response_model=DocumentSkeleton)
def get_skeleton(document_id: uuid.UUID, db: Session = Depends(get_db)) -> DocumentSkeleton:
    """설문 1·2단계 UI용 목차·개념·선행지식 후보."""
    return MaterialsService(db).get_skeleton(document_id)
