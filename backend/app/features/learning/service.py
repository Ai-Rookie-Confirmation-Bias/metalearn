"""[3.Service] 학습 서빙 유스케이스 — JIT 생성 트리거 / 확신도 / 절 서빙.

흐름(기획서 §2 5~7단계):
  POST /chapters/:id/generate → try_claim_generation(멱등) → 절별 생성 → ready
  POST /sections/:id/confidence → variant 결정·기록
  GET  /sections/:id → verified 블록 → variant 필터 → 정답 스트립 → 봉투 배열
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.enums import (
    ConfidenceLevel,
    ContentSource,
    GenStatus,
    MasteryStatus,
    ServeVariant,
)
from app.core.llm.factory import get_llm_client
from app.features.learning import repository as repo
from app.features.learning.generator import GenerationInput, generate_section_blocks
from app.features.learning.grading import GRADABLE_TYPES, GradeResult, grade_block
from app.features.learning.mastery import (
    MasteryState,
    apply_boolean_attempt,
    apply_scored_attempt,
    unlock_for_learning,
)
from app.features.learning.models import ConceptMastery
from app.features.learning.next_action import decide_after_answer
from app.features.learning.schemas import (
    AttemptFeedback,
    AttemptRequest,
    AttemptResponse,
    BlockEnvelope,
    ConceptStateOut,
    NextActionOut,
    SectionBlocksResponse,
)
from app.features.learning.serializer import filter_by_variant, to_envelope
from app.features.review.sm2 import update_review_schedule

logger = logging.getLogger(__name__)

# 확신도 → variant (기획서 §6: 알면 압축/모르면 풀)
_CONFIDENCE_TO_VARIANT: dict[str, str] = {
    ConfidenceLevel.SURE: ServeVariant.QUICK,
    ConfidenceLevel.AMBIGUOUS: ServeVariant.COMPRESSED,
    ConfidenceLevel.UNKNOWN: ServeVariant.FULL,
}


def variant_for_confidence(confidence: str) -> str:
    return _CONFIDENCE_TO_VARIANT.get(confidence, ServeVariant.FULL)


# ── JIT 생성 ─────────────────────────────────────────────────────────────────
async def _generate_one_section(
    db: Session, *, section, course, user_id: uuid.UUID
) -> int:
    """절 하나 생성→검증→저장. 반환: 저장된 블록 수."""
    concept = repo.get_concept(db, section.concept_id) if section.concept_id else None
    if concept is None:
        return 0

    # 근거 확보(§2.5A [1]) — book은 청크, ai_prereq는 외부근거
    chunks = (
        repo.get_concept_chunks(db, course=course, concept=concept)
        if concept.source == ContentSource.BOOK
        else []
    )
    ext_refs = (
        repo.get_concept_external_refs(db, concept.id)
        if concept.source == ContentSource.AI_PREREQ
        else []
    )

    # 난이도 힌트: 학습자 상태(mastery.difficulty)가 있으면 반영 — JIT 개인화 입력
    mastery = repo.get_mastery(db, user_id=user_id, concept_id=concept.id)
    difficulty_hint = 2
    if mastery is not None:
        # strength 기반 근사: 약하면 기초(1), 강하면 심화(3)
        difficulty_hint = 1 if mastery.strength < 0.35 else (3 if mastery.strength >= 0.7 else 2)

    drafts = await generate_section_blocks(
        get_llm_client(),
        GenerationInput(
            concept_name=concept.name,
            concept_description=concept.description,
            concept_source=concept.source,
            chunks=chunks,
            external_refs=ext_refs,
            difficulty_hint=difficulty_hint,
        ),
    )
    repo.replace_section_blocks(
        db, section_id=section.id, concept_id=concept.id, drafts=drafts
    )
    return len(drafts)


async def run_chapter_generation(chapter_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """백그라운드 태스크 본체. 자체 세션을 열고 끝나면 ready/failed 마킹."""
    db = SessionLocal()
    try:
        chapter = repo.get_chapter(db, chapter_id)
        if chapter is None:
            return
        course = repo.get_course_of_chapter(db, chapter)
        if course is None:
            repo.set_gen_status(db, chapter_id, GenStatus.FAILED)
            return

        total = 0
        for section in repo.get_chapter_sections(db, chapter_id):
            total += await _generate_one_section(
                db, section=section, course=course, user_id=user_id
            )
        db.commit()
        # 블록이 하나도 안 나오면 실패로 마킹(범위 갭 — 서빙할 게 없음)
        repo.set_gen_status(
            db, chapter_id, GenStatus.READY if total > 0 else GenStatus.FAILED
        )
    except Exception:
        logger.exception("chapter generation failed: %s", chapter_id)
        db.rollback()
        repo.set_gen_status(db, chapter_id, GenStatus.FAILED)
    finally:
        db.close()


def claim_generation(db: Session, chapter_id: uuid.UUID) -> str:
    """생성 트리거(멱등). 반환: 트리거 후 상태 문자열.

    이미 generating/ready면 그 상태를 그대로 알려준다(중복 생성 방지).
    """
    chapter = repo.get_chapter(db, chapter_id)
    if chapter is None:
        raise LookupError("chapter not found")
    if repo.try_claim_generation(db, chapter_id):
        return GenStatus.GENERATING
    db.refresh(chapter)
    return chapter.gen_status


# ── 확신도 → variant ─────────────────────────────────────────────────────────
def set_confidence(
    db: Session,
    *,
    user_id: uuid.UUID,
    section_id: uuid.UUID,
    confidence: str,
) -> tuple[str, str]:
    """확신도 기록 + variant 결정. 반환: (confidence, variant)."""
    section = repo.get_section(db, section_id)
    if section is None:
        raise LookupError("section not found")
    if section.concept_id is not None:
        repo.upsert_confidence(
            db, user_id=user_id, concept_id=section.concept_id, confidence=confidence
        )
    variant = variant_for_confidence(confidence)
    repo.upsert_section_variant(
        db, user_id=user_id, section_id=section_id, variant=variant
    )
    db.commit()
    return confidence, variant


# ── 절 서빙 ──────────────────────────────────────────────────────────────────
def serve_section(
    db: Session,
    *,
    user_id: uuid.UUID,
    section_id: uuid.UUID,
) -> SectionBlocksResponse:
    """절 블록 봉투 배열. verified만 → variant 필터 → 정답 스트립."""
    section = repo.get_section(db, section_id)
    if section is None:
        raise LookupError("section not found")

    progress = repo.get_section_progress(db, user_id=user_id, section_id=section_id)
    variant = (
        progress.variant_served
        if progress and progress.variant_served
        else ServeVariant.FULL
    )

    blocks = repo.get_verified_section_blocks(db, section_id)
    blocks = filter_by_variant(blocks, variant)

    # ai_prereq 인용 배지용 외부근거 일괄 로드(N+1 방지)
    ref_ids = [rid for b in blocks for rid in (b.external_ref_ids or [])]
    refs = repo.get_external_refs_by_ids(db, ref_ids)

    envelopes: list[BlockEnvelope] = [to_envelope(b, external_refs=refs) for b in blocks]
    return SectionBlocksResponse(
        section_id=str(section_id),
        concept_id=str(section.concept_id) if section.concept_id else None,
        variant=variant,
        blocks=envelopes,
    )


# ── 정답 기록 (§7 인출 / §8 추적) ────────────────────────────────────────────
def _build_mastery_state(
    db: Session, *, row: ConceptMastery, user_id: uuid.UUID, concept_id: uuid.UUID
) -> MasteryState:
    """DB 행 + attempts 집계 → 순수 MasteryState 스냅샷.

    시도수/연속오답은 컬럼에 저장하지 않고 append-only attempts에서 계산한다
    (기획 원칙: 파생값은 계산으로).
    """
    total, passed = repo.get_attempt_stats(db, user_id=user_id, concept_id=concept_id)
    streak = repo.get_consecutive_wrong(db, user_id=user_id, concept_id=concept_id)
    difficulty = 1 if row.strength < 0.35 else (3 if row.strength >= 0.7 else 2)
    return MasteryState(
        strength=row.strength,
        explanation_score=row.explanation_score,
        status=row.status,
        consecutive_wrong=streak,
        attempts=total,
        correct_count=passed,
        difficulty=difficulty,
    )


async def record_attempt(
    db: Session, *, user_id: uuid.UUID, req: AttemptRequest
) -> AttemptResponse:
    """POST /attempts 본체: 서버 채점 → 기록 → 숙련도/스케줄 갱신 → 다음 행동.

    한 트랜잭션: 채점(LLM 포함)은 잠금 밖에서, 상태 갱신은 mastery 행 잠금 안에서.
    """
    if req.block_id is None:
        raise ValueError("blockId가 필요합니다")
    block = repo.get_block(db, uuid.UUID(req.block_id))
    if block is None:
        raise LookupError("block not found")
    if block.type not in GRADABLE_TYPES:
        raise ValueError(f"채점 대상 블록이 아닙니다: {block.type}")

    concept_id = block.concept_id or (
        uuid.UUID(req.concept_id) if req.concept_id else None
    )
    if concept_id is None:
        raise ValueError("conceptId를 결정할 수 없습니다")

    # [1] 서버 채점 — 클라이언트가 보낸 correct는 신뢰하지 않는다
    result: GradeResult = await grade_block(
        get_llm_client(),
        block_type=block.type,
        block_data=block.data or {},
        user_input=req.user_input,
    )

    # [2] 숙련도 갱신 — 행 잠금(동시 제출 race 방지)
    mastery = repo.get_mastery_for_update(db, user_id=user_id, concept_id=concept_id)
    if mastery is None:
        mastery = ConceptMastery(
            user_id=user_id, concept_id=concept_id, status=MasteryStatus.TODO
        )
        db.add(mastery)
        db.flush()

    state = _build_mastery_state(
        db, row=mastery, user_id=user_id, concept_id=concept_id
    )
    state = unlock_for_learning(state)
    if result.score is not None:
        state = apply_scored_attempt(state, score=result.score)
    else:
        state = apply_boolean_attempt(state, correct=bool(result.correct))

    mastery.strength = state.strength
    mastery.explanation_score = state.explanation_score
    mastery.status = state.status

    # [3] 복습 스케줄(SM-2): review는 항상, learn은 통과 시(초기 스케줄 §9)
    if req.kind == "review" or result.passed:
        schedule = update_review_schedule(
            ease=mastery.ease,
            interval_days=mastery.interval_days,
            correct=result.correct,
            score=result.score,
        )
        mastery.ease = schedule.ease
        mastery.interval_days = schedule.interval_days
        mastery.next_due_at = schedule.next_due_at
        mastery.last_reviewed_at = datetime.now(timezone.utc)

    # [4] 다음 행동 결정(살아있는 커리큘럼 신호)
    action = decide_after_answer(state=state, is_correct=result.passed)

    # [5] attempts 기록(append-only) — 개입 신호/행동을 meta에 남긴다(§2.5C)
    feedback_dict = None
    if result.score is not None:
        feedback_dict = {
            "missedPoints": result.missed_points or [],
            "comment": result.comment or "",
        }
    repo.insert_attempt(
        db,
        user_id=user_id,
        block_id=block.id,
        concept_id=concept_id,
        kind=req.kind,
        correct=result.correct,
        score=result.score,
        user_input={"value": req.user_input} if req.user_input is not None else None,
        feedback=feedback_dict,
        meta={
            "blockType": block.type,
            "nextAction": action.action,
            "consecutiveWrong": state.consecutive_wrong,
            **(req.meta or {}),
        },
    )

    # [6] 절 진행/완료 판정: tracked 블록 전부 통과 → completed
    if block.section_id is not None:
        tracked_ids = repo.get_tracked_block_ids(db, block.section_id)
        passed_ids = repo.get_passed_block_ids(
            db, user_id=user_id, block_ids=tracked_ids
        )
        repo.mark_section_progress(
            db,
            user_id=user_id,
            section_id=block.section_id,
            completed=bool(tracked_ids) and passed_ids >= set(tracked_ids),
        )

    db.commit()

    return AttemptResponse(
        correct=result.correct,
        score=result.score,
        feedback=(
            AttemptFeedback(
                missed_points=result.missed_points or [], comment=result.comment or ""
            )
            if result.score is not None
            else None
        ),
        concept=ConceptStateOut(
            concept_id=str(concept_id),
            strength=mastery.strength,
            status=mastery.status,
            explanation_score=mastery.explanation_score,
            next_due_at=(
                mastery.next_due_at.isoformat() if mastery.next_due_at else None
            ),
        ),
        next_action=NextActionOut(action=action.action, reason=action.reason),
    )
