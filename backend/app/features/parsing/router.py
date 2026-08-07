"""파싱 라우터.

  POST /parsing/documents            업로드 → 백그라운드 파싱 시작
  GET  /parsing/documents/{id}       상태 조회 (프론트가 폴링)
  GET  /parsing/documents/{id}/tree  목차 + 조각 + 개념
"""
from __future__ import annotations

import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.deps import get_current_user_id
from app.features.parsing.models import MaterialRole
from app.features.parsing.schemas import ConceptHitOut, DocumentOut, DocumentTree
from app.features.parsing.service import ParsingService

router = APIRouter()


async def _run_pipeline(document_id: uuid.UUID, file_bytes: bytes) -> None:
    """백그라운드 실행. 요청 세션은 이미 닫혔으므로 세션을 새로 연다."""
    db = SessionLocal()
    try:
        await ParsingService(db).run(document_id, file_bytes)
    except Exception:  # noqa: BLE001 — 실패 사유는 service가 문서에 기록한다
        pass
    finally:
        db.close()


@router.post("/documents", response_model=DocumentOut, status_code=202)
async def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    role: str = MaterialRole.SKELETON.value,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> DocumentOut:
    """자료 업로드. 파싱은 백그라운드로 돌고 상태는 폴링으로 확인한다.

    같은 파일(지문 일치)이 이미 파싱돼 있으면 그대로 재사용한다 —
    문서가 공용이라 가능한 일이다. 그래도 **소유는 사람마다 따로 남는다**
    (user_documents). 그래서 남이 올려둔 책을 내가 올리면 파싱은 0초인데
    내 책장에는 새로 꽂힌다.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")

    service = ParsingService(db)
    document_id, needs_parse = service.register(
        file_bytes=file_bytes,
        filename=file.filename or "document.pdf",
        user_id=user_id,
        role=role,
    )
    if needs_parse:
        background.add_task(_run_pipeline, document_id, file_bytes)

    document = service.repo.get_document(document_id)
    return DocumentOut.model_validate(document)


@router.get("/concepts/search", response_model=list[ConceptHitOut])
async def search_concepts(
    q: str = Query(..., min_length=1, description="찾을 개념 이름이나 설명"),
    limit: int = Query(10, ge=1, le=50),
    min_sim: float = Query(0.0, ge=0.0, le=1.0),
    document_id: list[uuid.UUID] | None = Query(None),
    db: Session = Depends(get_db),
) -> list[ConceptHitOut]:
    """개념을 뜻으로 찾는다. **문서 경계를 넘는다.**

    이름이 안 겹쳐도 찾는다 — "소프트웨어 비용 산정"으로 검색하면 이름에 그
    말이 없는 "COCOMO 모형"이 올라온다. 자료 간 개념 매칭과 외부 조달이
    이 위에 올라간다.

    document_id를 여러 번 주면 그 자료들 안에서만 찾는다.
    """
    return await ParsingService(db).search_concepts(
        q, limit=limit, document_ids=document_id, min_sim=min_sim
    )


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_status(document_id: uuid.UUID, db: Session = Depends(get_db)) -> DocumentOut:
    document = ParsingService(db).repo.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    return DocumentOut.model_validate(document)


@router.get("/documents/{document_id}/tree", response_model=DocumentTree)
def get_tree(document_id: uuid.UUID, db: Session = Depends(get_db)) -> DocumentTree:
    try:
        return ParsingService(db).get_tree(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
