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

from app.core.enums import ChapterOrigin, EdgeKind, GenStatus, MasteryStatus
from app.features.curriculum.models import Chapter, Section
from app.features.learning.generator import BlockDraft, ChunkExcerpt, ExternalRefInput
from app.features.learning.models import (
    Attempt,
    Block,
    ConceptMastery,
    Enrollment,
    LearningCursor,
    SectionProgress,
)
from app.features.materials.models import DocChunk, Document
from app.features.seed.models import Concept, ConceptEdge, Course, ExternalRef


def _course_doc_ids(db: Session, course: Course) -> list[uuid.UUID]:
    """코스가 소유한 모든 문서 id(primary+supplementary). RAG는 보조자료도 근거로.

    다중 PDF(1:N): Document.course_id로 귀속. 하위호환: 없으면 course.document_id.
    """
    ids = list(
        db.scalars(select(Document.id).where(Document.course_id == course.id))
    )
    if not ids and course.document_id is not None:
        ids = [course.document_id]
    return ids


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


# ── 선행 삽입(살아있는 커리큘럼, ISSUE-002) ──────────────────────────────────
def find_section_by_concept(
    db: Session, *, course_id: uuid.UUID, concept_id: uuid.UUID
) -> Section | None:
    """코스 내에서 개념에 매핑된 절(있으면). 선행 삽입 멱등성 판단에 사용."""
    stmt = (
        select(Section)
        .join(Chapter, Section.chapter_id == Chapter.id)
        .where(Chapter.course_id == course_id, Section.concept_id == concept_id)
        .order_by(Section.order_index)
    )
    return db.scalars(stmt).first()


def insert_prerequisite_chapter(
    db: Session, *, course_id: uuid.UUID, concept: Concept, before_order: int
) -> tuple[Chapter, Section]:
    """선행 개념용 chapter(origin='prereq', pending) + section 1개를 현재 챕터 앞에 생성.

    학습자가 선행을 먼저 밟게 before_order-5에 끼운다. JIT 생성은 프론트가 새 챕터로
    라우팅하며 기존 `POST /chapters/:id/generate` 트리거로 태운다(여기선 pending만).
    """
    chapter = Chapter(
        course_id=course_id,
        order_index=before_order - 5,
        title=f"[선행] {concept.name}",
        origin=ChapterOrigin.PREREQ,
        gen_status=GenStatus.PENDING,
    )
    db.add(chapter)
    db.flush()
    section = Section(
        chapter_id=chapter.id,
        concept_id=concept.id,
        order_index=10,
        title=concept.name,
    )
    db.add(section)
    db.flush()
    return chapter, section


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
    """절의 학습 블록을 새 세트로 교체(재생성 대응). 진단 블록은 절에 안 묶이므로 무관.

    이미 푼 블록은 attempts가 FK로 참조하므로, 블록 삭제 전 그 attempts를 먼저
    지운다(재생성되면 옛 블록 답변 기록은 무의미). mastery는 별도 테이블이라 보존.
    """
    old_ids = select(Block.id).where(Block.section_id == section_id)
    db.query(Attempt).filter(Attempt.block_id.in_(old_ids)).delete(
        synchronize_session=False
    )
    db.query(Block).filter(Block.section_id == section_id).delete(
        synchronize_session=False
    )
    rows: list[Block] = []
    for i, d in enumerate(drafts):
        rows.append(
            Block(
                section_id=section_id,
                order_index=i,
                type=d.type,
                kind=d.kind or "learn",
                concept_id=d.concept_id or concept_id,
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
        .where(DocChunk.document_id.in_(_course_doc_ids(db, course)))
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


def search_concept_chunks(
    db: Session,
    *,
    course: Course,
    concept: Concept,
    query_embedding: list[float] | None,
    limit: int = 3,
) -> list[ChunkExcerpt]:
    """개념 근거 청크 검색(RAG, ISSUE-004). 임베딩 유사도(pgvector cosine) 우선.

    임베딩이 없거나(상류 미색인) 결과가 비면 키워드+앞청크(get_concept_chunks)로 폴백.
    문서 필터 후 풀스캔(4096차원은 인덱스 불가) — 문서 단위라 규모 감당.
    """
    if query_embedding is not None:
        stmt = (
            select(DocChunk)
            .where(
                DocChunk.document_id.in_(_course_doc_ids(db, course)),
                DocChunk.embedding.isnot(None),
            )
            .order_by(DocChunk.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )
        picked = list(db.scalars(stmt))
        if picked:
            return [ChunkExcerpt(id=c.id, content=c.content) for c in picked]
    return get_concept_chunks(db, course=course, concept=concept, limit=limit)


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


# ── placement 시딩(진단 종료 → 수준 체크 진입점) ─────────────────────────────
def get_enrollment(
    db: Session, *, user_id: uuid.UUID, course_id: uuid.UUID
) -> Enrollment | None:
    return db.get(Enrollment, (user_id, course_id))


def get_course_concepts(db: Session, course_id: uuid.UUID) -> list[Concept]:
    stmt = select(Concept).where(Concept.course_id == course_id)
    return list(db.scalars(stmt))


def get_curriculum_order(
    db: Session, course_id: uuid.UUID
) -> dict[uuid.UUID, int]:
    """섹션에 매핑된 개념의 커리큘럼 진행 좌표. concept_id → chapter*1000+section order.

    parsing 규약의 진행축(문서/커리큘럼 순서)을 placement가 쓰기 위한 좌표.
    섹션 없는 개념(순수 선행)은 포함하지 않는다(진행선에 없음).
    """
    stmt = (
        select(Section.concept_id, Chapter.order_index, Section.order_index)
        .join(Chapter, Section.chapter_id == Chapter.id)
        .where(Chapter.course_id == course_id, Section.concept_id.isnot(None))
    )
    out: dict[uuid.UUID, int] = {}
    for concept_id, ch_order, sec_order in db.execute(stmt):
        out[concept_id] = ch_order * 1000 + sec_order
    return out


def seed_mastery_if_absent(
    db: Session,
    *,
    user_id: uuid.UUID,
    seeds: list[tuple[uuid.UUID, str, float]],
) -> tuple[int, int]:
    """concept_mastery 초기 시딩. seeds=[(concept_id, status, strength), ...].

    진단↔커리큘럼 화해(ISSUE-013, 병합 v2): 진단(BKT)이 모든 개념의 mastery
    행을 status='locked'(기본값)으로 미리 만들어 두면, 예전 'if_absent'는
    전부 스킵해 커리큘럼이 status를 못 깔았다(전 개념 locked → 콘텐츠 미표시).
    이제 **기본 locked 상태인 행은 placement status로 갱신**하고, 실제 학습이
    진행된 행(status가 todo/learning/mastered로 이미 바뀐 것)은 보존한다.
    반환: (신규+갱신 수, 보존/스킵 수).
    """
    existing: dict[uuid.UUID, ConceptMastery] = {
        m.concept_id: m
        for m in db.scalars(
            select(ConceptMastery).where(ConceptMastery.user_id == user_id)
        )
    }
    applied = 0
    new_rows: list[ConceptMastery] = []
    for concept_id, status, strength in seeds:
        row = existing.get(concept_id)
        if row is None:
            new_rows.append(
                ConceptMastery(
                    user_id=user_id,
                    concept_id=concept_id,
                    status=status,
                    strength=strength,
                )
            )
            applied += 1
        elif row.status == MasteryStatus.LOCKED:
            # 진단이 만들어 둔 기본 locked 행 → placement 판정으로 status 확정.
            # strength는 진단 신호가 있으면(>기본값) 보존, 없으면 placement 값.
            row.status = status
            if not row.strength or row.strength <= strength:
                row.strength = strength
            applied += 1
    if new_rows:
        db.add_all(new_rows)
    db.flush()
    return applied, len(seeds) - applied


# ── 원인 국소화(BKT×DAG, ISSUE-010) ──────────────────────────────────────────
def get_prerequisite_ids(db: Session, concept_id: uuid.UUID) -> list[uuid.UUID]:
    """개념의 직접 선행 id들. **parsing 규약**: 엣지 from(의존) → to(선행), kind=prerequisite.

    즉 대상 X의 선행 = {e.to_concept_id : e.from_concept_id == X, kind=prerequisite}.
    (신호는 엣지로만 전파 — 직접 선행만 반환. 방향 규약: docs/GRAPH_ORIENTATION_CONTRACT.md)
    """
    stmt = select(ConceptEdge.to_concept_id).where(
        ConceptEdge.from_concept_id == concept_id,
        ConceptEdge.kind == EdgeKind.PREREQUISITE,
    )
    return list(db.scalars(stmt))


def get_concept_depths(
    db: Session, concept_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """개념 id → depth_level(DAG 최장경로 좌표). None은 0으로 본다."""
    if not concept_ids:
        return {}
    stmt = select(Concept.id, Concept.depth_level).where(Concept.id.in_(concept_ids))
    return {cid: (depth or 0) for cid, depth in db.execute(stmt)}


def get_strength_map(
    db: Session, *, user_id: uuid.UUID, concept_ids: list[uuid.UUID]
) -> dict[uuid.UUID, float]:
    """개념 id → concept_mastery.strength(선행 P(known) 프록시). 행 없으면 생략."""
    if not concept_ids:
        return {}
    stmt = select(ConceptMastery.concept_id, ConceptMastery.strength).where(
        ConceptMastery.user_id == user_id,
        ConceptMastery.concept_id.in_(concept_ids),
    )
    return {cid: strength for cid, strength in db.execute(stmt)}


def get_concept_outcomes(
    db: Session, *, user_id: uuid.UUID, concept_id: uuid.UUID, limit: int = 50
) -> list[bool]:
    """개념의 정오 시퀀스(시간순, BKT 접기 입력). 채점된 learn/review 시도만."""
    stmt = (
        select(Attempt.correct, Attempt.score)
        .where(
            Attempt.user_id == user_id,
            Attempt.concept_id == concept_id,
            Attempt.kind.in_(["learn", "review"]),
            (Attempt.correct.isnot(None)) | (Attempt.score.isnot(None)),
        )
        .order_by(Attempt.created_at)
        .limit(limit)
    )
    outcomes: list[bool] = []
    for correct, score in db.execute(stmt):
        passed = bool(correct) if correct is not None else (score or 0) >= 0.6
        outcomes.append(passed)
    return outcomes


# ── 복습 조회(SM-2 next_due, ISSUE 복습9) ────────────────────────────────────
_REVIEW_SECTION_TITLE = "복습 · 오답 체크"


def get_or_create_review_section(db: Session, chapter_id: uuid.UUID) -> Section:
    """챕터 맨 앞 복습 섹션 — concept_id=NULL, order_index=0."""
    for s in get_chapter_sections(db, chapter_id):
        if s.concept_id is None and s.title.startswith("복습"):
            return s
    section = Section(
        chapter_id=chapter_id,
        order_index=0,
        title=_REVIEW_SECTION_TITLE,
        concept_id=None,
    )
    db.add(section)
    db.flush()
    return section


def get_wrong_note_concepts(
    db: Session,
    *,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    limit: int = 5,
) -> list[tuple[Concept, str]]:
    """오답노트 후보 — attempts 파생(별도 테이블 없음). 반환: (개념, 이유 라벨).

    연속 오답 ≥1 또는 strength<0.4(시도 있음). 최근 2연속 정답이면 청산(제외).
    이유 라벨(변화 가시성, SERVICE_OVERVIEW §4): 커리큘럼은 말없이 변하지 않는다 —
    이 카드가 '왜' 나왔는지를 서버가 문장으로 내려준다.
    """
    stmt = (
        select(Concept, ConceptMastery)
        .join(ConceptMastery, ConceptMastery.concept_id == Concept.id)
        .where(Concept.course_id == course_id, ConceptMastery.user_id == user_id)
    )
    candidates: list[tuple[Concept, ConceptMastery]] = [
        (c, m) for c, m in db.execute(stmt)
    ]
    scored: list[tuple[float, Concept, str]] = []
    for concept, mastery in candidates:
        streak = get_consecutive_wrong(
            db, user_id=user_id, concept_id=concept.id
        )
        total, _ = get_attempt_stats(db, user_id=user_id, concept_id=concept.id)
        if total >= 2 and streak == 0 and mastery.strength >= 0.8:
            continue  # 청산
        if streak >= 1:
            reason = (
                f"지난 학습에서 {streak}번 연속 틀렸던 개념이에요 — "
                "다음 장에 들어가기 전에 다시 짚어요"
                if streak >= 2
                else "지난 학습에서 틀렸던 개념이에요 — 잊기 전에 다시 짚어요"
            )
            scored.append((float(streak), concept, reason))
        elif total > 0 and mastery.strength < 0.4:
            scored.append(
                (0.0, concept, "아직 확실히 익히지 못한 개념이에요 — 한 번 더 꺼내볼까요")
            )
    scored.sort(key=lambda x: (-x[0], x[1].name))
    return [(c, reason) for _, c, reason in scored[:limit]]


def _sm2_due_reason(mastery: ConceptMastery, now: datetime) -> str:
    """SM-2 도래 개념의 이유 라벨 — '5일 전 배운 개념, 잊힐 때가 됐어요'."""
    if mastery.last_reviewed_at is None:
        return "복습 시점이 된 개념이에요 — 기억이 사라지기 전에 다시 꺼내요"
    days = max(0, (now - mastery.last_reviewed_at).days)
    when = "오늘" if days == 0 else f"{days}일 전"
    return f"{when} 배운 개념, 잊힐 때가 됐어요 — 망각 곡선이 복습을 권해요"


def collect_review_concepts(
    db: Session,
    *,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    limit: int = 5,
) -> list[tuple[Concept, str]]:
    """다음 장 맨 앞 복습 페이로드 — 오답노트 우선, SM-2 due 보조. (개념, 이유)."""
    now = datetime.now(timezone.utc)
    wrong = get_wrong_note_concepts(
        db, user_id=user_id, course_id=course_id, limit=limit
    )
    seen = {c.id for c, _ in wrong}
    due_rows = get_due_masteries(
        db, user_id=user_id, course_id=course_id, now=now, limit=limit
    )
    merged = list(wrong)
    for m, concept in due_rows:
        if concept.id not in seen:
            merged.append((concept, _sm2_due_reason(m, now)))
            seen.add(concept.id)
        if len(merged) >= limit:
            break
    return merged[:limit]


def get_due_masteries(
    db: Session,
    *,
    user_id: uuid.UUID,
    course_id: uuid.UUID | None,
    now: datetime,
    limit: int = 20,
) -> list[tuple[ConceptMastery, Concept]]:
    """복습 도래 = next_due_at <= now. (개념명·코스 필터 위해 concepts 조인)."""
    conds = [
        ConceptMastery.user_id == user_id,
        ConceptMastery.next_due_at.isnot(None),
        ConceptMastery.next_due_at <= now,
    ]
    if course_id is not None:
        conds.append(Concept.course_id == course_id)
    stmt = (
        select(ConceptMastery, Concept)
        .join(Concept, Concept.id == ConceptMastery.concept_id)
        .where(*conds)
        .order_by(ConceptMastery.next_due_at)
        .limit(limit)
    )
    return [(m, c) for m, c in db.execute(stmt)]


def get_schedule_masteries(
    db: Session,
    *,
    user_id: uuid.UUID,
    course_id: uuid.UUID | None,
    limit: int = 100,
) -> list[tuple[ConceptMastery, Concept]]:
    """다가오는 복습 캘린더 = next_due_at 있는 개념(도래 여부 무관), 임박순."""
    conds = [
        ConceptMastery.user_id == user_id,
        ConceptMastery.next_due_at.isnot(None),
    ]
    if course_id is not None:
        conds.append(Concept.course_id == course_id)
    stmt = (
        select(ConceptMastery, Concept)
        .join(Concept, Concept.id == ConceptMastery.concept_id)
        .where(*conds)
        .order_by(ConceptMastery.next_due_at)
        .limit(limit)
    )
    return [(m, c) for m, c in db.execute(stmt)]


def get_review_block(db: Session, section_id: uuid.UUID) -> Block | None:
    """복습으로 다시 답할 블록 1개 — 절의 tracked+verified 중 첫 블록."""
    stmt = (
        select(Block)
        .where(
            Block.section_id == section_id,
            Block.tracked.is_(True),
            Block.verified.is_(True),
        )
        .order_by(Block.order_index)
        .limit(1)
    )
    return db.scalars(stmt).first()


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


# ── 보충(재설명) — 개입 사다리 ②(ISSUE-005) ─────────────────────────────────
def get_latest_attempt_for_block(
    db: Session, *, user_id: uuid.UUID, block_id: uuid.UUID
) -> Attempt | None:
    """이 블록에 대한 이 학습자의 최근 시도(보충 생성의 오답 입력)."""
    stmt = (
        select(Attempt)
        .where(Attempt.user_id == user_id, Attempt.block_id == block_id)
        .order_by(Attempt.created_at.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()


def attach_attempt_analysis(
    db: Session, *, attempt_id: uuid.UUID, diagnosis: str, misconception: bool
) -> None:
    """보충 생성의 진단 결과를 해당 시도 meta에 남긴다(append-only 원칙 위배 아님 —
    행 추가가 아니라 같은 시도의 후속 분석을 병합). 다음 국소화·복습 생성의 재료."""
    row = db.get(Attempt, attempt_id)
    if row is None:
        return
    row.meta = {
        **(row.meta or {}),
        "supplement": {"diagnosis": diagnosis, "misconception": misconception},
    }
    db.flush()


def get_recent_misconception(
    db: Session, *, user_id: uuid.UUID, concept_id: uuid.UUID
) -> bool:
    """직전 시도의 보충 진단에 오개념 신호가 있었는지(localize misconception_signal).

    가장 최근 시도 하나만 본다 — 그 뒤에 새 시도(정답 포함)가 쌓이면 meta가 없어
    자연히 꺼진다(오래된 오개념 판정이 계속 발화하는 것 방지)."""
    stmt = (
        select(Attempt.meta)
        .where(
            Attempt.user_id == user_id,
            Attempt.concept_id == concept_id,
            Attempt.kind.in_(["learn", "review"]),
        )
        .order_by(Attempt.created_at.desc())
        .limit(1)
    )
    meta = db.scalar(stmt) or {}
    return bool((meta.get("supplement") or {}).get("misconception"))


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


def get_attempted_block_ids(
    db: Session, *, user_id: uuid.UUID, block_ids: list[uuid.UUID]
) -> set[uuid.UUID]:
    """유저가 한 번이라도 시도(정오답 무관)한 블록 ID 집합.

    진행 게이트용(진단 재설계 §2.2): 인출은 '맞혀야 통과'가 아니라 '풀면 진행'.
    오답은 그대로 BKT·오답노트로 흘러가 다음 장 복습으로 재출제된다 — 내용을
    막지 않고 데이터로 삼는다. (mastery/strength는 정오답을 별도로 반영.)
    """
    if not block_ids:
        return set()
    stmt = select(Attempt.block_id).where(
        Attempt.user_id == user_id,
        Attempt.block_id.in_(block_ids),
    )
    return {bid for bid in db.scalars(stmt) if bid is not None}


# ── 학습 커서(복귀 자동화, ISSUE-002) ────────────────────────────────────────
def get_cursor(
    db: Session, *, user_id: uuid.UUID, course_id: uuid.UUID
) -> LearningCursor | None:
    return db.get(LearningCursor, (user_id, course_id))


def _get_or_create_cursor(
    db: Session, *, user_id: uuid.UUID, course_id: uuid.UUID
) -> LearningCursor:
    cur = db.get(LearningCursor, (user_id, course_id))
    if cur is None:
        cur = LearningCursor(
            user_id=user_id, course_id=course_id, return_stack=[]
        )
        db.add(cur)
        db.flush()
    return cur


def push_and_enter(
    db: Session,
    *,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    from_section_id: uuid.UUID,
    to_section_id: uuid.UUID,
) -> LearningCursor:
    """현재 절을 복귀 스택에 push하고 커서를 선행 절(to)로 이동. 중첩 선행 대응(LIFO).

    from이 이미 스택 top이면 재push하지 않는다(같은 절 반복 실패 시 중복 방지).
    """
    cur = _get_or_create_cursor(db, user_id=user_id, course_id=course_id)
    stack = list(cur.return_stack or [])
    token = str(from_section_id)
    if not stack or stack[-1] != token:
        stack.append(token)
    cur.return_stack = stack  # 재할당으로 JSONB 변경 감지
    cur.current_section_id = to_section_id
    cur.updated_at = datetime.now(timezone.utc)
    db.flush()
    return cur


def pop_return(
    db: Session, *, user_id: uuid.UUID, course_id: uuid.UUID
) -> uuid.UUID | None:
    """복귀 스택 pop → 커서를 그 절로 이동하고 반환. 스택 비면 None(커서 유지)."""
    cur = db.get(LearningCursor, (user_id, course_id))
    if cur is None or not cur.return_stack:
        return None
    stack = list(cur.return_stack)
    token = stack.pop()
    cur.return_stack = stack
    resume_id = uuid.UUID(token)
    cur.current_section_id = resume_id
    cur.updated_at = datetime.now(timezone.utc)
    db.flush()
    return resume_id


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
