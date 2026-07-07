"""[1.Controller] 문서 섭취 API (documents → courses → concepts)."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.documents.schemas import CourseDetail, CourseSummary
from app.features.documents.service import DocumentService

router = APIRouter()

_MAX_UPLOAD_BYTES = 30 * 1024 * 1024  # 30MB


@router.post("/upload", response_model=CourseDetail, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> CourseDetail:
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=415, detail="PDF 파일만 지원합니다.")
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")
    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="파일이 너무 큽니다(최대 30MB).")
    return await DocumentService(db).ingest(
        file_bytes=file_bytes,
        filename=file.filename or "upload.pdf",
        title=title,
    )


@router.get("/courses", response_model=list[CourseSummary])
def list_courses(db: Session = Depends(get_db)) -> list[CourseSummary]:
    return DocumentService(db).list_courses()


@router.get("/courses/{course_id}", response_model=CourseDetail)
def get_course(course_id: int, db: Session = Depends(get_db)) -> CourseDetail:
    return DocumentService(db).get_course_detail(course_id)
