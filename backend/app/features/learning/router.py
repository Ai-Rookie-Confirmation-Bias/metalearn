"""[1.Controller] 학습 서빙 API (docs/API.md 진단/생성/학습 섹션의 학습 파트).

  POST /chapters/{id}/generate  — JIT 생성 트리거(멱등, 백그라운드)
  GET  /chapters/{id}           — gen_status 폴링
  POST /sections/{id}/confidence — 확신도 → variant
  GET  /sections/{id}           — 절 블록 서빙(verified만, 정답 스트립)

경로가 docs/API.md와 일치하도록 prefix 없이 등록한다(app/api.py 참고).
"""
from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.enums import GenStatus
from app.features.learning import repository as repo
from app.features.learning import service
from app.features.learning.generator import _block_claim_text
from app.features.learning.schemas import (
    AttemptRequest,
    AttemptResponse,
    ChapterStatusResponse,
    ConfidenceRequest,
    ConfidenceResponse,
    CursorResponse,
    GenerateTriggerResponse,
    PlacementResponse,
    ChunkEvidenceResponse,
    EvidencePassage,
    NoteResponse,
    PageContentItem,
    PageContentResponse,
    NoteSaveRequest,
    OfflinePackBlock,
    OfflinePackResponse,
    ReadCompleteResponse,
    SectionBlocksResponse,
    SupplementResponse,
    TutorChatRequest,
    TutorChatResponse,
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


@router.post("/blocks/{block_id}/supplement", response_model=SupplementResponse)
async def post_block_supplement(
    block_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> SupplementResponse:
    """오답 블록의 맞춤 보충(재설명) — next_action=supplement의 실체(ISSUE-005).

    최근 시도가 오답일 때만 생성한다(정답/무시도는 422). 채점(POST /attempts)과
    분리해 reveal은 즉시, 재설명은 뒤따라 도착하는 구조.
    """
    try:
        return await service.generate_block_supplement(
            db, user_id=user_id, block_id=block_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


_WORD_RE = re.compile(r"[가-힣]{2,}|[A-Za-z]{3,}")
_IMG_MD_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_EVIDENCE_MIN_OVERLAP = 2  # 블록 키워드와 이만큼 겹치는 문단만 근거 후보
_EVIDENCE_MAX_PASSAGES = 12  # 그중 겹침 점수 상위 N개까지(넓은 원문 방지)


def _split_paragraphs(content: str) -> list[str]:
    """청크 마크다운 → 문단 리스트. 이미지 마크다운·짧은 목차 라인 제거."""
    text = _IMG_MD_RE.sub("", content)
    parts = re.split(r"\n\s*\n|\n", text)
    return [p.strip().lstrip("#").strip() for p in parts if len(p.strip()) > 15]


def _select_evidence(
    paragraphs: list[tuple[str, int | None]], claim: str
) -> list[tuple[str, int | None]]:
    """블록 텍스트(claim)와 키워드 겹침이 큰 문단만 추린다(원문 순서 유지).

    청크가 섹션 단위로 커서 전체를 보이면 근거가 "이 책 어딘가"가 된다 →
    블록과 실제 관련된 문단만 남겨 좁힌다. 겹침 후보가 없으면 전체 폴백.
    """
    words = set(_WORD_RE.findall(claim))
    if not words:
        return paragraphs
    scored = [
        (len(words & set(_WORD_RE.findall(text))), i, text, page)
        for i, (text, page) in enumerate(paragraphs)
    ]
    hits = [s for s in scored if s[0] >= _EVIDENCE_MIN_OVERLAP]
    if not hits:
        return paragraphs
    top = sorted(hits, key=lambda s: -s[0])[:_EVIDENCE_MAX_PASSAGES]
    top.sort(key=lambda s: s[1])  # 원문 순서로 복원
    out: list[tuple[str, int | None]] = []
    seen: set[str] = set()
    for _, _, text, page in top:  # 반복 헤딩 등 중복 문단 제거
        if text in seen:
            continue
        seen.add(text)
        out.append((text, page))
    return out


@router.get("/chunks/evidence", response_model=ChunkEvidenceResponse)
def get_chunk_evidence(
    ids: str,
    blockId: str | None = None,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ChunkEvidenceResponse:
    """근거 보기 — 배지가 가리키는 청크 원문 중 블록 관련 문단만(추적 가능한 AI).

    ids: 쉼표로 구분한 청크 UUID(잘못된 토큰 무시). blockId가 있으면 그 블록과
    관련된 문단만 추려 좁힌다(없으면 청크 전체 문단).
    """
    chunk_ids: list[uuid.UUID] = []
    for tok in ids.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            chunk_ids.append(uuid.UUID(tok))
        except ValueError:
            continue
    chunks = repo.get_chunks_by_ids(db, chunk_ids)

    # 청크들 → (문단, 페이지) 평탄화
    paragraphs: list[tuple[str, int | None]] = []
    doc_id: str | None = None
    for c in chunks:
        if doc_id is None and c.document_id:
            doc_id = str(c.document_id)
        for para in _split_paragraphs(c.content):
            paragraphs.append((para, c.page_from))

    # blockId가 있으면 블록 텍스트로 관련 문단만 좁힌다
    if blockId:
        try:
            block = repo.get_block(db, uuid.UUID(blockId))
        except ValueError:
            block = None
        if block is not None:
            claim = _block_claim_text(block.type, block.data or {})
            paragraphs = _select_evidence(paragraphs, claim)

    # "언급된 페이지"는 청크 전체 범위가 아니라 **좁힌 근거 문단들의 페이지**로.
    pages = [p for _, p in paragraphs if p is not None]
    return ChunkEvidenceResponse(
        passages=[EvidencePassage(text=t, page=p) for t, p in paragraphs],
        document_id=doc_id,
        page_from=min(pages) if pages else None,
        page_to=max(pages) if pages else None,
    )


@router.get("/documents/page-content", response_model=PageContentResponse)
def get_page_content(
    documentId: str,
    pageFrom: int,
    pageTo: int,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> PageContentResponse:
    """언급된 페이지 전체 보기 — 근거 맥락 확장(refined_elements 페이지 경계)."""
    try:
        doc_uuid = uuid.UUID(documentId)
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid documentId")
    items = repo.get_page_content(db, doc_uuid, pageFrom, pageTo)
    return PageContentResponse(
        items=[PageContentItem(page=pg, text=t) for pg, t in items]
    )


@router.get("/sections/{section_id}/offline-pack", response_model=OfflinePackResponse)
def get_offline_pack(
    section_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> OfflinePackResponse:
    """오프라인 채점 팩 — **정답 포함**(스트립 안 함). 온디바이스 이중구조(제안서 ④).

    소비자는 사용자 기기의 로컬 엔진 어댑터(ondevice/adapter.py)다: 온라인일 때
    미리 받아 두고, 서버가 안 닿으면 로컬 sLLM(EXAONE 1.2B)이 채점을 이어받는다.
    브라우저 학습 UI는 이 경로를 쓰지 않는다(치팅 방지 스트립은 GET /sections/:id 그대로).
    """
    section = repo.get_section(db, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="section not found")
    concept = (
        repo.get_concept(db, section.concept_id) if section.concept_id else None
    )
    blocks = repo.get_verified_section_blocks(db, section_id)
    return OfflinePackResponse(
        section_id=str(section_id),
        title=section.title,
        concept_name=concept.name if concept else None,
        blocks=[
            OfflinePackBlock(
                id=str(b.id),
                type=b.type,
                concept_id=str(b.concept_id) if b.concept_id else None,
                tracked=b.tracked,
                data=b.data or {},
            )
            for b in blocks
        ],
    )


@router.get("/sections/{section_id}/note", response_model=NoteResponse)
def get_section_note(
    section_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> NoteResponse:
    """나의 요약 노트 조회 — 없으면 빈 노트(404 아님, 탭 열 때마다 호출)."""
    note = repo.get_study_note(db, user_id=user_id, section_id=section_id)
    if note is None:
        return NoteResponse(section_id=str(section_id))
    return NoteResponse(
        section_id=str(section_id),
        content=note.content,
        updated_at=note.updated_at.isoformat() if note.updated_at else None,
    )


@router.put("/sections/{section_id}/note", response_model=NoteResponse)
def put_section_note(
    section_id: uuid.UUID,
    body: NoteSaveRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> NoteResponse:
    """나의 요약 노트 저장(upsert) — 자기설명 메모의 영속화(원리 ② 흔적)."""
    if repo.get_section(db, section_id) is None:
        raise HTTPException(status_code=404, detail="section not found")
    note = repo.upsert_study_note(
        db, user_id=user_id, section_id=section_id, content=body.content
    )
    db.commit()
    return NoteResponse(
        section_id=str(section_id),
        content=note.content,
        updated_at=note.updated_at.isoformat() if note.updated_at else None,
    )


@router.post("/tutor/chat", response_model=TutorChatResponse)
async def post_tutor_chat(
    body: TutorChatRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> TutorChatResponse:
    """AI 튜터 Q&A — 현재 절 근거 접지 + 정답 비유출(소크라틱, tutor.py 규칙)."""
    try:
        return await service.tutor_chat(db, user_id=user_id, req=body)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/courses/{course_id}/cursor", response_model=CursorResponse)
def get_learning_cursor(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> CursorResponse:
    """현재 학습 위치 + 복귀 대기 깊이(선행 우회 중이면 돌아갈 절이 쌓여 있음)."""
    return service.get_cursor(db, user_id=user_id, course_id=course_id)


@router.post("/courses/{course_id}/placement", response_model=PlacementResponse)
def initialize_course_placement(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> PlacementResponse:
    """진단 종료 후 floor/ceiling 기준 concept_mastery 시딩(수준 체크 진입점).

    계약상 진단 종료 흐름이 service.initialize_placement를 직접 호출하는 게 정석이나,
    지금은 단독 검증/수동 트리거용으로 엔드포인트로도 노출한다(임시 이음새).
    """
    try:
        return service.initialize_placement(db, user_id=user_id, course_id=course_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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


@router.post(
    "/sections/{section_id}/read-complete", response_model=ReadCompleteResponse
)
def complete_section_reading(
    section_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ReadCompleteResponse:
    """tracked 0개 절(예: analogy만 있는 선행 절)의 열람 완료 처리.

    채점 대상 블록이 하나라도 있으면 409 — 그런 절은 인출을 풀어야 완료된다.
    완료 시 커서 복귀 pop까지 record_attempt와 동일하게 수행한다(판단은 서버).
    """
    try:
        return service.complete_section_by_reading(
            db, user_id=user_id, section_id=section_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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
