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


async def _run_batch_background(
    anchor_document_id: uuid.UUID, course_id: uuid.UUID, docs: list[dict]
) -> None:
    """다중 PDF 백그라운드 파이프라인 — 새 DB 세션."""
    db = SessionLocal()
    try:
        await DocumentService(db).run_batch_pipeline(
            anchor_document_id=anchor_document_id, course_id=course_id, docs=docs
        )
    except Exception:  # noqa: BLE001 — 실패 상태는 run_batch_pipeline이 앵커에 기록
        _log.exception("백그라운드 배치 ingest 실패 (course=%s)", course_id)
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


@router.post("/upload-batch", response_model=None, status_code=201)
async def upload_batch(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    roles: list[str] = Form(default=[]),
    title: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """다중 PDF 업로드 — 순서대로 하나의 코스로 통합.

    files 순서 = 학습 순서(프론트가 파일명 정렬/드래그로 확정해 전송).
    roles[i]는 files[i]와 병렬: 'primary'(교재 척추) | 'supplementary'(RAG 근거).
    primary들이 순서 유지한 채 앞으로, supplementary는 뒤로 모아 ingest.
    """
    if not files:
        raise HTTPException(status_code=400, detail="파일이 없습니다.")
    items: list[dict] = []
    for i, f in enumerate(files):
        if f.content_type not in ("application/pdf", "application/octet-stream"):
            raise HTTPException(status_code=415, detail="PDF 파일만 지원합니다.")
        data = await f.read()
        if not data:
            raise HTTPException(status_code=400, detail="빈 파일이 있습니다.")
        if len(data) > _MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="파일이 너무 큽니다(최대 30MB).")
        role = roles[i] if i < len(roles) else "primary"
        items.append({
            "filename": f.filename or f"upload{i}.pdf",
            "role": role if role in ("primary", "supplementary") else "primary",
            "bytes": data,
        })

    primaries = [it for it in items if it["role"] == "primary"]
    supps = [it for it in items if it["role"] == "supplementary"]
    if not primaries:
        raise HTTPException(status_code=400, detail="주교재(primary) 최소 1개가 필요합니다.")
    ordered = primaries + supps

    service = DocumentService(db)
    anchor_id, course_id, specs = service.create_batch_stub(
        files=[{"filename": it["filename"], "role": it["role"]} for it in ordered],
        title=title,
    )
    docs = [
        {
            "document_id": specs[i]["document_id"],
            "role": specs[i]["role"],
            "filename": ordered[i]["filename"],
            "file_bytes": ordered[i]["bytes"],
        }
        for i in range(len(ordered))
    ]
    background_tasks.add_task(_run_batch_background, anchor_id, course_id, docs)
    return {
        "document_id": str(anchor_id),
        "id": str(course_id),
        "course_id": str(course_id),
        "status": "processing",
        "document_count": len(ordered),
    }


@router.get("/courses", response_model=list[CourseSummary])
def list_courses(db: Session = Depends(get_db)) -> list[CourseSummary]:
    return DocumentService(db).list_courses()


@router.get("/courses/{course_id}", response_model=CourseDetail)
def get_course(course_id: uuid.UUID, db: Session = Depends(get_db)) -> CourseDetail:
    return DocumentService(db).get_course_detail(course_id)
