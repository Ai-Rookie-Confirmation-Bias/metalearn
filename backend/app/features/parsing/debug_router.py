"""단계별 수동 실행 라우터 — 파싱을 한 칸씩 돌려보는 개발용 도구.

  GET  /parsing/debug/steps            단계 목록 (프론트가 버튼을 그린다)
  POST /parsing/debug/documents        업로드만 (파싱 안 돌림)
  GET  /parsing/debug/{id}/state       어디까지 했는지 + 산출물 개수
  POST /parsing/debug/{id}/steps/{step} 그 단계 하나만 실행
  GET  /parsing/debug/{id}/raw         1단계 원문 전체 (자르지 않음)
  GET  /parsing/debug/{id}/figures/{fid} 그림 이미지 (눈으로 확인용)
"""
from __future__ import annotations

import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.parsing.debug_service import STEPS, DebugService
from app.features.parsing.models import DocFigure

router = APIRouter()


@router.get("/steps")
def list_steps() -> list[dict]:
    return STEPS


@router.post("/documents", status_code=201)
async def upload(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> dict:
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")

    service = DebugService(db)
    document_id = service.upload(
        file_bytes=file_bytes, filename=file.filename or "document.pdf"
    )
    return service.state(document_id)


@router.get("/{document_id}/state")
def get_state(document_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    try:
        return DebugService(db).state(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{document_id}/raw")
def get_raw(document_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    """Document Parse 결과 원본. 요소 전체를 자르지 않고 그대로 준다."""
    try:
        return DebugService(db).raw(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{document_id}/steps/{step}")
async def run_step(
    document_id: uuid.UUID, step: str, db: Session = Depends(get_db)
) -> dict:
    service = DebugService(db)
    try:
        result = await service.run_step(document_id, step)
    except ValueError as exc:
        # 순서를 안 지켰거나(선행 단계 미실행) 검산 실패 — 사용자가 고칠 수 있다.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — 디버그 도구라 사유를 그대로 보여준다
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"{type(exc).__name__}: {exc}"
        ) from exc

    return {"result": asdict(result), "state": service.state(document_id)}


@router.get("/{document_id}/figures/{figure_id}")
def get_figure(
    document_id: uuid.UUID, figure_id: uuid.UUID, db: Session = Depends(get_db)
) -> Response:
    """그림 원본 이미지. 비전 판정이 맞는지 눈으로 보려면 필요하다."""
    figure = db.get(DocFigure, figure_id)
    if figure is None or figure.document_id != document_id:
        raise HTTPException(status_code=404, detail="그림을 찾을 수 없습니다.")
    return Response(content=figure.data, media_type=figure.mime)
