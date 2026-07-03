"""[4.Repository] 학습 루프 DB 접근.

서비스가 필요로 하는 영속 연산만 얇게 제공한다:
  - 챕터/절/블록 조회
  - gen_status 원자 전이(트리거 멱등성 — 새로고침 연타 방어)
  - 블록 일괄 저장(재생성 시 기존 학습 블록 교체)
  - 개념 근거(청크/외부근거) 조회 — 생성 입력
  - 확신도/variant 기록(concept_mastery, section_progress upsert)
"""
from __future__ import annotations

import uuid

from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.enums import GenStatus
from app.features.curriculum.models import Chapter, Section
from app.features.learning.generator import BlockDraft, ChunkExcerpt, ExternalRefInput
from app.features.learning.models import (
    Attempt,
    Block,
    ConceptMastery,
    SectionProgress,
)
from app.features.materials.models import DocChunk
from app.features.seed.models import Concept, Course, ExternalRef


# ── 챕터 / 절 ────────────────────────────────────────────────────────────────
def get_chapter(db: Session, chapter_id: uuid.UUID) -> Chapter | None:
    return db.get(Chapter, chapter_id)


def get_section(db: Session, section_id: uuid.UUID) -> Section | None:
    return db.get(Section, section_id)


def get_chapter_sections(db: Session, chapter_id: uuid.UUID) -> list[Section]:
    stmt = (
        select(Section)
        .where(Section.chapter_id == chapter_id)
        .order_by(Section.order_index)
    )
    return list(db.scalars(stmt))


def get_course_of_chapter(db: Session, chapter: Chapter) -> Course | None:
    return db.get(Course, chapter.course_id)


# ── gen_status 원자 전이 ─────────────────────────────────────────────────────
def try_claim_generation(db: Session, chapter_id: uuid.UUID) -> bool:
    """pending/failed → generating 조건부 전이. 이미 generating/ready면 False.

    UPDATE ... WHERE gen_status IN (...) 한 방으로 동시 트리거 경합을 막는다.
    """
    stmt = (
        update(Chapter)
        .where(
            Chapter.id == chapter_id,
            Chapter.gen_status.in_([GenStatus.PENDING, GenStatus.FAILED]),
        )
        .values(gen_status=GenStatus.GENERATING)
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount > 0


def set_gen_status(db: Session, chapter_id: uuid.UUID, status: str) -> None:
    db.execute(update(Chapter).where(Chapter.id == chapter_id).values(gen_status=status))
    db.commit()


# ── 블록 ─────────────────────────────────────────────────────────────────────
def replace_section_blocks(
    db: Session,
    *,
    section_id: uuid.UUID,
    concept_id: uuid.UUID | None,
    drafts: list[BlockDraft],
) -> list[Block]:
    """절의 학습 블록을 새 세트로 교체(재생성 대응). 진단 블록은 절에 안 묶이므로 무관."""
    db.query(Block).filter(Block.section_id == section_id).delete()
    rows: list[Block] = []
    for i, d in enumerate(drafts):
        rows.append(
            Block(
                section_id=section_id,
                order_index=i,
                type=d.type,
                kind="learn",
                concept_id=concept_id,
                source=d.source,
                tracked=d.tracked,
                source_chunk_ids=d.source_chunk_ids,
                external_ref_ids=d.external_ref_ids,
                verified=d.verified,
                data=d.data,
                meta=d.meta,
            )
        )
    db.add_all(rows)
    db.flush()
    return rows


def get_verified_section_blocks(db: Session, section_id: uuid.UUID) -> list[Block]:
    """서빙 대상 = verified=true 뿐(기획서 불변식)."""
    stmt = (
        select(Block)
        .where(Block.section_id == section_id, Block.verified.is_(True))
        .order_by(Block.order_index)
    )
    return list(db.scalars(stmt))


# ── 생성 근거 ────────────────────────────────────────────────────────────────
def get_concept(db: Session, concept_id: uuid.UUID) -> Concept | None:
    return db.get(Concept, concept_id)


def get_concept_chunks(
    db: Session, *, course: Course, concept: Concept, limit: int = 3
) -> list[ChunkExcerpt]:
    """개념 관련 청크 발췌(생성 근거).

    MVP: 개념 이름/키 토큰 포함 청크를 우선, 부족하면 문서 앞 청크로 보충.
    TODO(후속): pgvector 임베딩 유사도 검색으로 교체(core/retrieval).
    """
    stmt = (
        select(DocChunk)
        .where(DocChunk.document_id == course.document_id)
        .order_by(DocChunk.chunk_index)
    )
    chunks = list(db.scalars(stmt))
    tokens = [t for t in {concept.name, concept.key} if t]
    scored = [c for c in chunks if any(t in c.content for t in tokens)]
    picked = scored[:limit]
    if len(picked) < limit:
        seen = {c.id for c in picked}
        picked += [c for c in chunks if c.id not in seen][: limit - len(picked)]
    return [ChunkExcerpt(id=c.id, content=c.content) for c in picked]


def get_concept_external_refs(
    db: Session, concept_id: uuid.UUID
) -> list[ExternalRefInput]:
    stmt = select(ExternalRef).where(ExternalRef.concept_id == concept_id)
    return [
        ExternalRefInput(id=r.id, title=r.title, url=r.url, snippet=r.snippet)
        for r in db.scalars(stmt)
    ]


def get_external_refs_by_ids(
    db: Session, ref_ids: list[uuid.UUID]
) -> dict[uuid.UUID, ExternalRef]:
    if not ref_ids:
        return {}
    stmt = select(ExternalRef).where(ExternalRef.id.in_(ref_ids))
    return {r.id: r for r in db.scalars(stmt)}


# ── 학습자 상태(확신도 / variant) ────────────────────────────────────────────
def get_mastery(
    db: Session, *, user_id: uuid.UUID, concept_id: uuid.UUID
) -> ConceptMastery | None:
    return db.get(ConceptMastery, (user_id, concept_id))


def upsert_confidence(
    db: Session, *, user_id: uuid.UUID, concept_id: uuid.UUID, confidence: str
) -> ConceptMastery:
    row = db.get(ConceptMastery, (user_id, concept_id))
    if row is None:
        row = ConceptMastery(user_id=user_id, concept_id=concept_id, confidence=confidence)
        db.add(row)
    else:
        row.confidence = confidence
    db.flush()
    return row


def get_section_progress(
    db: Session, *, user_id: uuid.UUID, section_id: uuid.UUID
) -> SectionProgress | None:
    return db.get(SectionProgress, (user_id, section_id))


def upsert_section_variant(
    db: Session, *, user_id: uuid.UUID, section_id: uuid.UUID, variant: str
) -> SectionProgress:
    row = db.get(SectionProgress, (user_id, section_id))
    if row is None:
        row = SectionProgress(
            user_id=user_id,
            section_id=section_id,
            status="in_progress",
            variant_served=variant,
        )
        db.add(row)
    else:
        row.variant_served = variant
        if row.status == "not_started":
            row.status = "in_progress"
    db.flush()
    return row


# ── 시도(attempts) 기록/집계 ─────────────────────────────────────────────────
def get_block(db: Session, block_id: uuid.UUID) -> Block | None:
    return db.get(Block, block_id)


def get_mastery_for_update(
    db: Session, *, user_id: uuid.UUID, concept_id: uuid.UUID
) -> ConceptMastery | None:
    """동시 제출 race 방지: 행 잠금 후 반환(없으면 None — 호출측에서 생성)."""
    stmt = (
        select(ConceptMastery)
        .where(
            ConceptMastery.user_id == user_id,
            ConceptMastery.concept_id == concept_id,
        )
        .with_for_update()
    )
    return db.scalars(stmt).first()


def get_attempt_stats(
    db: Session, *, user_id: uuid.UUID, concept_id: uuid.UUID
) -> tuple[int, int]:
    """(집계된 시도 수, 통과 수). learn/review의 채점된 시도만 센다."""
    base = select(func.count()).where(
        Attempt.user_id == user_id,
        Attempt.concept_id == concept_id,
        Attempt.kind.in_(["learn", "review"]),
        (Attempt.correct.isnot(None)) | (Attempt.score.isnot(None)),
    )
    total = db.scalar(base) or 0
    passed = (
        db.scalar(
            select(func.count()).where(
                Attempt.user_id == user_id,
                Attempt.concept_id == concept_id,
                Attempt.kind.in_(["learn", "review"]),
                (Attempt.correct.is_(True)) | (Attempt.score >= 0.6),
            )
        )
        or 0
    )
    return total, passed


def get_consecutive_wrong(
    db: Session, *, user_id: uuid.UUID, concept_id: uuid.UUID, limit: int = 10
) -> int:
    """최근 시도부터 거슬러 올라가며 연속 오답 수(막힘 감지 신호)."""
    stmt = (
        select(Attempt.correct, Attempt.score)
        .where(
            Attempt.user_id == user_id,
            Attempt.concept_id == concept_id,
            Attempt.kind.in_(["learn", "review"]),
            (Attempt.correct.isnot(None)) | (Attempt.score.isnot(None)),
        )
        .order_by(Attempt.created_at.desc())
        .limit(limit)
    )
    streak = 0
    for correct, score in db.execute(stmt):
        passed = bool(correct) if correct is not None else (score or 0) >= 0.6
        if passed:
            break
        streak += 1
    return streak


def insert_attempt(
    db: Session,
    *,
    user_id: uuid.UUID,
    block_id: uuid.UUID | None,
    concept_id: uuid.UUID,
    kind: str,
    correct: bool | None,
    score: float | None,
    user_input: dict | None,
    feedback: dict | None,
    meta: dict,
) -> Attempt:
    row = Attempt(
        user_id=user_id,
        block_id=block_id,
        concept_id=concept_id,
        kind=kind,
        correct=correct,
        score=score,
        user_input=user_input,
        feedback=feedback,
        meta=meta,
    )
    db.add(row)
    db.flush()
    return row


# ── 절 완료 판정 ─────────────────────────────────────────────────────────────
def get_tracked_block_ids(db: Session, section_id: uuid.UUID) -> list[uuid.UUID]:
    stmt = select(Block.id).where(
        Block.section_id == section_id,
        Block.tracked.is_(True),
        Block.verified.is_(True),
    )
    return list(db.scalars(stmt))


def get_passed_block_ids(
    db: Session, *, user_id: uuid.UUID, block_ids: list[uuid.UUID]
) -> set[uuid.UUID]:
    """유저가 통과(정답 또는 score>=0.6)한 블록 ID 집합."""
    if not block_ids:
        return set()
    stmt = select(Attempt.block_id).where(
        Attempt.user_id == user_id,
        Attempt.block_id.in_(block_ids),
        (Attempt.correct.is_(True)) | (Attempt.score >= 0.6),
    )
    return {bid for bid in db.scalars(stmt) if bid is not None}


def mark_section_progress(
    db: Session, *, user_id: uuid.UUID, section_id: uuid.UUID, completed: bool
) -> SectionProgress:
    row = db.get(SectionProgress, (user_id, section_id))
    if row is None:
        row = SectionProgress(user_id=user_id, section_id=section_id)
        db.add(row)
    if completed:
        row.status = "completed"
        row.completed_at = datetime.now(timezone.utc)
    elif row.status == "not_started":
        row.status = "in_progress"
    db.flush()
    return row
