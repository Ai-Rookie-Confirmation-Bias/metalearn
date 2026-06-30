"""[1.Controller] 학습 자료 섭취(Ingestion) API."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.materials.schemas import MaterialDetail, MaterialSummary
from app.features.materials.service import MaterialService

router = APIRouter()

_MAX_UPLOAD_BYTES = 30 * 1024 * 1024  # 30MB


@router.post("/upload", response_model=MaterialDetail, status_code=201)
async def upload_material(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> MaterialDetail:
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=415, detail="PDF 파일만 지원합니다.")
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")
    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="파일이 너무 큽니다(최대 30MB).")
    return await MaterialService(db).ingest(
        file_bytes=file_bytes,
        filename=file.filename or "upload.pdf",
        title=title,
    )


@router.get("", response_model=list[MaterialSummary])
def list_materials(db: Session = Depends(get_db)) -> list[MaterialSummary]:
    return MaterialService(db).list_materials()


@router.get("/{material_id}", response_model=MaterialDetail)
def get_material(material_id: int, db: Session = Depends(get_db)) -> MaterialDetail:
    return MaterialService(db).get_detail(material_id)
