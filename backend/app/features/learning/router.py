"""[1.Controller] 학습 서빙 API (docs/API.md 진단/생성/학습 섹션의 학습 파트).

  POST /chapters/{id}/generate  — JIT 생성 트리거(멱등, 백그라운드)
  GET  /chapters/{id}           — gen_status 폴링
  POST /sections/{id}/confidence — 확신도 → variant
  GET  /sections/{id}           — 절 블록 서빙(verified만, 정답 스트립)

경로가 docs/API.md와 일치하도록 prefix 없이 등록한다(app/api.py 참고).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.enums import GenStatus
from app.features.learning import repository as repo
from app.features.learning import service
from app.features.learning.schemas import (
    AttemptRequest,
    AttemptResponse,
    ChapterStatusResponse,
    ConfidenceRequest,
    ConfidenceResponse,
    GenerateTriggerResponse,
    SectionBlocksResponse,
)

router = APIRouter()


@router.post("/attempts", response_model=AttemptResponse)
async def post_attempt(
    body: AttemptRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> AttemptResponse:
    """정답 기록(§7). 서버가 채점하고 숙련도·복습 스케줄·절 진행을 갱신한다."""
    try:
        return await service.record_attempt(db, user_id=user_id, req=body)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/chapters/{chapter_id}/generate", response_model=GenerateTriggerResponse)
def trigger_chapter_generation(
    chapter_id: uuid.UUID,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> GenerateTriggerResponse:
    """생성 트리거. 이미 generating/ready면 그 상태만 반환(중복 생성 없음)."""
    try:
        status = service.claim_generation(db, chapter_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if status == GenStatus.GENERATING:
        background.add_task(service.run_chapter_generation, chapter_id, user_id)
    return GenerateTriggerResponse(chapter_id=str(chapter_id), gen_status=status)


@router.get("/chapters/{chapter_id}", response_model=ChapterStatusResponse)
def get_chapter_status(
    chapter_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ChapterStatusResponse:
    chapter = repo.get_chapter(db, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail="chapter not found")
    sections = repo.get_chapter_sections(db, chapter_id)
    return ChapterStatusResponse(
        chapter_id=str(chapter.id),
        title=chapter.title,
        origin=chapter.origin,
        gen_status=chapter.gen_status,
        section_ids=[str(s.id) for s in sections],
    )


@router.post("/sections/{section_id}/confidence", response_model=ConfidenceResponse)
def set_section_confidence(
    section_id: uuid.UUID,
    body: ConfidenceRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ConfidenceResponse:
    try:
        confidence, variant = service.set_confidence(
            db, user_id=user_id, section_id=section_id, confidence=body.confidence
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ConfidenceResponse(
        section_id=str(section_id), confidence=confidence, variant=variant
    )


@router.get("/sections/{section_id}", response_model=SectionBlocksResponse)
def get_section_blocks(
    section_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> SectionBlocksResponse:
    try:
        return service.serve_section(db, user_id=user_id, section_id=section_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
