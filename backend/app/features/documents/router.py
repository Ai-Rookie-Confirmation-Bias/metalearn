"""[1.Controller] 문서 섭취 API (documents → courses → concepts). (병합 2단계: UUID)

비동기 ingest (ISSUE-010②): 업로드는 즉시 스텁(course_id + processing)을
돌려주고 파이프라인은 백그라운드 실행. 진행 상태는 GET /courses/{id}의
status로 폴링(processing→parsing→refining→chunking→extracting→
building_seed→ready|failed).
"""
import logging
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.features.documents.schemas import CourseDetail, CourseSummary
from app.features.documents.service import DocumentService

router = APIRouter()

_log = logging.getLogger("uvicorn.error")

_MAX_UPLOAD_BYTES = 30 * 1024 * 1024  # 30MB


async def _run_pipeline_background(
    document_id: uuid.UUID, course_id: uuid.UUID, file_bytes: bytes, filename: str
) -> None:
    """백그라운드 파이프라인 — 요청 세션과 분리된 새 DB 세션 사용."""
    db = SessionLocal()
    try:
        await DocumentService(db).run_pipeline(
            document_id=document_id,
            course_id=course_id,
            file_bytes=file_bytes,
            filename=filename,
        )
    except Exception:  # noqa: BLE001 — 실패 상태는 run_pipeline이 document에 기록
        _log.exception("백그라운드 ingest 실패 (document=%s)", document_id)
    finally:
        db.close()


@router.post("/upload", response_model=None, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    background: bool = Form(default=True),
    db: Session = Depends(get_db),
) -> CourseDetail | dict:
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=415, detail="PDF 파일만 지원합니다.")
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")
    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="파일이 너무 큽니다(최대 30MB).")

    service = DocumentService(db)
    filename = file.filename or "upload.pdf"
    if not background:
        return await service.ingest(file_bytes=file_bytes, filename=filename, title=title)

    document_id, course_id = service.create_stub(filename=filename, title=title)
    background_tasks.add_task(
        _run_pipeline_background, document_id, course_id, file_bytes, filename
    )
    return {
        "document_id": str(document_id),
        "id": str(course_id),  # 프론트 호환: 업로드 응답의 id = course_id
        "course_id": str(course_id),
        "status": "processing",
    }


@router.get("/courses", response_model=list[CourseSummary])
def list_courses(db: Session = Depends(get_db)) -> list[CourseSummary]:
    return DocumentService(db).list_courses()


@router.get("/courses/{course_id}", response_model=CourseDetail)
def get_course(course_id: uuid.UUID, db: Session = Depends(get_db)) -> CourseDetail:
    return DocumentService(db).get_course_detail(course_id)
