"""[3.Service] 학습 서빙 유스케이스 — JIT 생성 트리거 / 확신도 / 절 서빙.

흐름(기획서 §2 5~7단계):
  POST /chapters/:id/generate → try_claim_generation(멱등) → 절별 생성 → ready
  POST /sections/:id/confidence → variant 결정·기록
  GET  /sections/:id → verified 블록 → variant 필터 → 정답 스트립 → 봉투 배열
"""
from __future__ import annotations

import asyncio
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
from app.features.learning.bkt import estimate_p_known, p_l0_from_prereqs
from app.features.learning.generator import GenerationInput, generate_section_blocks
from app.features.learning.grading import GRADABLE_TYPES, GradeResult, grade_block
from app.features.learning.localization import Cause, PrereqState, localize
from app.features.learning.mastery import (
    MasteryState,
    apply_boolean_attempt,
    apply_scored_attempt,
    classify_placement,
    unlock_for_learning,
)
from app.features.learning.models import ConceptMastery
from app.features.learning.next_action import decide_after_answer
from app.features.learning.schemas import (
    AttemptFeedback,
    AttemptRequest,
    AttemptResponse,
    BlockEnvelope,
    CauseOut,
    ConceptStateOut,
    CursorResponse,
    NextActionOut,
    PlacementResponse,
    PrerequisiteTargetOut,
    RevealOut,
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


# ── placement 시딩 (진단 종료 → 수준 체크 진입점) ─────────────────────────────
def initialize_placement(
    db: Session, *, user_id: uuid.UUID, course_id: uuid.UUID
) -> PlacementResponse:
    """placement(학습자 배치) 초기 시딩 — 커리큘럼 생성 단계의 진입점.

    ── placement란? ──
    학습자를 지식 그래프/커리큘럼 위 **어디에서 시작할지** 배치하는 것(반편성).
    진단평가(**parsing 담당**)가 두 좌표를 산출한다:
      · floor(바닥)   = 이미 아는 가장 윗지점 = 학습 시작점(그 아래는 안다고 보고 건너뜀)
      · ceiling(천장) = 학습 목표점(거기까지 도달이 목표)
    이 함수는 그 좌표를 받아 concept_mastery 초기 상태를 깐다:
      floor 아래 → mastered / floor~ceiling → todo / ceiling 위 → locked.

    ── 경계(중요) ──
    수준 **판정** 자체는 진단평가(parsing)의 산출물이다. 우리 영역은 "진단 후 →
    커리큘럼 생성"부터. 그래서 이 함수의 역할은 *판정 계산*이 아니라 **판정 수령·기록·
    킥오프**다. 현재는 floor/ceiling에서 커리큘럼 순서로 근사 계산하지만, 병합 시
    parsing의 진단 mastery 판정을 그대로 수령하고 진단 안 한 개념만 위치로 채우는 쪽으로
    좁힌다(ISSUE-013). 진단 종료 흐름이 이 함수를 호출하는 것이 계약(지금은 라우터로도 노출).
    멱등: 이미 상태가 있는 개념(학습 진행)은 보존한다.
    """
    enrollment = repo.get_enrollment(db, user_id=user_id, course_id=course_id)
    if enrollment is None:
        raise LookupError("enrollment not found")
    if enrollment.ceiling_concept is None:
        raise ValueError("진단 미완료: ceiling_concept이 없습니다")

    # 진행축 = 커리큘럼 순서(parsing 규약). 섹션에 매핑된 개념(진행선)만 시딩한다.
    order_by_id = repo.get_curriculum_order(db, course_id)
    ceiling_pos = order_by_id.get(enrollment.ceiling_concept)
    floor_pos = (
        order_by_id.get(enrollment.floor_concept)
        if enrollment.floor_found and enrollment.floor_concept is not None
        else None
    )

    seeds: list[tuple[uuid.UUID, str, float]] = []
    counts = {MasteryStatus.MASTERED: 0, MasteryStatus.TODO: 0, MasteryStatus.LOCKED: 0}
    for concept_id, position in order_by_id.items():
        seed = classify_placement(
            position, floor_position=floor_pos, ceiling_position=ceiling_pos
        )
        seeds.append((concept_id, seed.status, seed.strength))
        counts[seed.status] = counts.get(seed.status, 0) + 1

    seeded, skipped = repo.seed_mastery_if_absent(db, user_id=user_id, seeds=seeds)
    db.commit()

    return PlacementResponse(
        course_id=str(course_id),
        floor_concept_id=(
            str(enrollment.floor_concept) if enrollment.floor_concept else None
        ),
        ceiling_concept_id=str(enrollment.ceiling_concept),
        seeded=seeded,
        skipped=skipped,
        mastered=counts[MasteryStatus.MASTERED],
        todo=counts[MasteryStatus.TODO],
        locked=counts[MasteryStatus.LOCKED],
    )


# ── JIT 생성 ─────────────────────────────────────────────────────────────────
async def _prepare_generation_input(
    db: Session, *, section, course, user_id: uuid.UUID
) -> GenerationInput | None:
    """절 하나의 생성 입력(근거·난이도)을 수집한다. 개념 없으면 None.

    DB 접근은 전부 이 직렬 수집 단계에 모은다 — sync Session은 태스크 간 동시
    사용이 안전하지 않으므로, 병렬 구간에는 순수 계층(generator)만 태운다(원칙 ①).
    """
    concept = repo.get_concept(db, section.concept_id) if section.concept_id else None
    if concept is None:
        return None

    # 근거 확보(§2.5A [1]) — book은 청크(RAG), ai_prereq는 외부근거
    # RAG(ISSUE-004): 개념을 query 임베딩 → 청크(passage) cosine top-K. 임베딩 없으면 키워드 폴백.
    # (병합 후엔 parsing이 저장한 concepts.embedding 소비로 전환 — 재임베딩 회피)
    chunks: list = []
    if concept.source == ContentSource.BOOK:
        query_emb: list[float] | None = None
        try:
            query_text = f"{concept.name}. {concept.description or ''}".strip()
            query_emb = await get_llm_client().embed(query_text, purpose="query")
        except Exception:  # noqa: BLE001 — 임베딩 실패 시 키워드 폴백
            logger.warning("개념 질의 임베딩 실패 → 키워드 폴백: %s", concept.name)
        chunks = repo.search_concept_chunks(
            db, course=course, concept=concept, query_embedding=query_emb
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

    return GenerationInput(
        concept_name=concept.name,
        concept_description=concept.description,
        concept_source=concept.source,
        chunks=chunks,
        external_refs=ext_refs,
        difficulty_hint=difficulty_hint,
    )


async def run_chapter_generation(chapter_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """백그라운드 태스크 본체. 자체 세션을 열고 끝나면 ready/failed 마킹.

    3단계 파이프라인: [수집(직렬 DB)] → [생성(절 단위 병렬 LLM)] → [저장(직렬 DB)].
    절을 순차로 돌리면 챕터당 LLM 콜이 전부 직렬이라, LLM 구간만 gather로 병렬화.
    동시 요청 상한은 Solar 클라이언트 전역 세마포어가 잡는다(429 방지).
    """
    db = SessionLocal()
    try:
        chapter = repo.get_chapter(db, chapter_id)
        if chapter is None:
            return
        course = repo.get_course_of_chapter(db, chapter)
        if course is None:
            repo.set_gen_status(db, chapter_id, GenStatus.FAILED)
            return

        # [수집] 절별 생성 입력 — DB·임베딩(직렬)
        plans: list[tuple[object, GenerationInput]] = []
        for section in repo.get_chapter_sections(db, chapter_id):
            inp = await _prepare_generation_input(
                db, section=section, course=course, user_id=user_id
            )
            if inp is not None:
                plans.append((section, inp))

        # [생성] 순수 계층만 병렬 실행 — 한 절이 실패해도 나머지는 계속(부분 성공 허용)
        results = await asyncio.gather(
            *(generate_section_blocks(get_llm_client(), inp) for _, inp in plans),
            return_exceptions=True,
        )

        # [저장] 직렬 저장
        total = 0
        for (section, _), drafts in zip(plans, results):
            if isinstance(drafts, BaseException):
                logger.error(
                    "절 생성 실패 — 건너뜀: section=%s", section.id, exc_info=drafts
                )
                continue
            repo.replace_section_blocks(
                db, section_id=section.id, concept_id=section.concept_id, drafts=drafts
            )
            total += len(drafts)
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
        id=str(section_id),
        title=section.title,
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


def _localize_cause(
    db: Session,
    *,
    user_id: uuid.UUID,
    concept_id: uuid.UUID,
    current_passed: bool,
    misconception_signal: bool = False,
) -> Cause:
    """원인 국소화(ISSUE-010): BKT P(known) + 선행 DAG로 "왜 틀렸나"를 판정.

    선행 P(known)은 concept_mastery.strength를 프록시로 쓴다(행 없으면 중립 0.5).
    현재 시도 결과를 정오 시퀀스에 포함해 추정한다.
    """
    outcomes = repo.get_concept_outcomes(db, user_id=user_id, concept_id=concept_id)
    outcomes = outcomes + [current_passed]

    prereq_ids = repo.get_prerequisite_ids(db, concept_id)
    strengths = repo.get_strength_map(db, user_id=user_id, concept_ids=prereq_ids)
    depths = repo.get_concept_depths(db, prereq_ids)
    # 행 없는 선행 = 미학습 → 0.0(결손). parsing 모델은 선행을 placement로 시딩 안 하므로
    # "안 본 선행 = gap"이 맞다(대상 시도수로 이미 hold 게이트가 걸려 오탐 방지됨).
    prereq_p = [strengths.get(pid, 0.0) for pid in prereq_ids]

    p_l0 = p_l0_from_prereqs(prereq_p)
    target_p_known = estimate_p_known(outcomes, p_l0=p_l0)
    prereqs = [
        PrereqState(
            concept_id=str(pid),
            p_known=strengths.get(pid, 0.0),
            depth=depths.get(pid, 0),
        )
        for pid in prereq_ids
    ]
    return localize(
        target_p_known=target_p_known,
        target_attempts=len(outcomes),
        prereqs=prereqs,
        misconception_signal=misconception_signal,
    )


def _course_id_of_section(db: Session, section_id: uuid.UUID) -> uuid.UUID | None:
    section = repo.get_section(db, section_id)
    chapter = repo.get_chapter(db, section.chapter_id) if section else None
    return chapter.course_id if chapter else None


def get_cursor(
    db: Session, *, user_id: uuid.UUID, course_id: uuid.UUID
) -> CursorResponse:
    """현재 학습 위치 + 복귀 대기 깊이. 프론트가 '지금 어디/돌아갈 데 있나'를 안다."""
    cursor = repo.get_cursor(db, user_id=user_id, course_id=course_id)
    if cursor is None:
        return CursorResponse(course_id=str(course_id), current_section_id=None, return_depth=0)
    return CursorResponse(
        course_id=str(course_id),
        current_section_id=(
            str(cursor.current_section_id) if cursor.current_section_id else None
        ),
        return_depth=len(cursor.return_stack or []),
    )


def _ensure_prerequisite_target(
    db: Session, *, user_id: uuid.UUID, block, blame_concept_id: uuid.UUID
) -> PrerequisiteTargetOut | None:
    """선행 삽입(ISSUE-002): blame 개념의 학습 지점을 멱등 보장하고 대상 표면화.

    이미 절이 있으면 그리로 라우팅(중복 삽입 금지). 없으면(순수 선행) 현재 챕터 앞에
    prereq 챕터+절을 만든다. + 학습 커서: 현재 절을 복귀 스택에 push하고 선행 절로 이동.
    JIT 생성/복귀 라우팅은 프론트가 반환된 대상으로 처리한다.
    """
    if block.section_id is None:
        return None  # 진단 등 절 맥락 없는 블록
    section = repo.get_section(db, block.section_id)
    chapter = repo.get_chapter(db, section.chapter_id) if section else None
    blame = repo.get_concept(db, blame_concept_id)
    if chapter is None or blame is None:
        return None

    existing = repo.find_section_by_concept(
        db, course_id=chapter.course_id, concept_id=blame_concept_id
    )
    if existing is not None:
        target_chapter = repo.get_chapter(db, existing.chapter_id)
        target_section, created = existing, False
    else:
        target_chapter, target_section = repo.insert_prerequisite_chapter(
            db,
            course_id=chapter.course_id,
            concept=blame,
            before_order=chapter.order_index,
        )
        created = True

    # 커서: 지금 절(block.section_id)을 복귀 스택에 쌓고 선행 절로 이동
    repo.push_and_enter(
        db,
        user_id=user_id,
        course_id=chapter.course_id,
        from_section_id=block.section_id,
        to_section_id=target_section.id,
    )

    return PrerequisiteTargetOut(
        concept_id=str(blame_concept_id),
        chapter_id=str(target_chapter.id),
        section_id=str(target_section.id),
        title=target_section.title,
        gen_status=target_chapter.gen_status,
        created=created,
    )


def _build_reveal(block) -> RevealOut | None:
    """채점 후 공개할 정답/해설(유출 아님). mcq=정답+해설, cloze=정답들. 그 외 None."""
    data = block.data or {}
    if block.type == "mcq":
        return RevealOut(
            answer_index=data.get("answerIndex"), explanation=data.get("explanation")
        )
    if block.type == "cloze":
        return RevealOut(blanks=data.get("blanks"))
    return None


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

    # [4b] 원인 국소화(ISSUE-010): 선수결손 vs 본문 결손 vs 판단 보류 + blame 선행
    cause = _localize_cause(
        db, user_id=user_id, concept_id=concept_id, current_passed=result.passed
    )

    # [4c] 선행 삽입(ISSUE-002): 틀렸고 원인이 선수결손이면 blame 선행 학습지점을 보장.
    #      cause 구동(Router의 거친 신호가 아니라) — content면 삽입 안 함. 성공 시엔 미개입.
    prerequisite_target = None
    if (
        not result.passed
        and cause.type == "prerequisite"
        and cause.blame_concept_id is not None
    ):
        prerequisite_target = _ensure_prerequisite_target(
            db,
            user_id=user_id,
            block=block,
            blame_concept_id=uuid.UUID(cause.blame_concept_id),
        )

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
            "cause": cause.type,
            **(
                {"blameConceptId": cause.blame_concept_id}
                if cause.blame_concept_id
                else {}
            ),
            **(
                {"prereqChapterId": prerequisite_target.chapter_id}
                if prerequisite_target
                else {}
            ),
            **(req.meta or {}),
        },
    )

    # [6] 절 진행/완료 판정: tracked 블록 전부 통과 → completed
    resume_section_id: str | None = None
    if block.section_id is not None:
        tracked_ids = repo.get_tracked_block_ids(db, block.section_id)
        passed_ids = repo.get_passed_block_ids(
            db, user_id=user_id, block_ids=tracked_ids
        )
        completed = bool(tracked_ids) and passed_ids >= set(tracked_ids)
        repo.mark_section_progress(
            db, user_id=user_id, section_id=block.section_id, completed=completed
        )
        # [6b] 커서: 완료한 절이 현재 위치면 복귀 스택 pop → 복귀 지점 표면화
        if completed:
            course_id = _course_id_of_section(db, block.section_id)
            cursor = (
                repo.get_cursor(db, user_id=user_id, course_id=course_id)
                if course_id
                else None
            )
            if cursor and cursor.current_section_id == block.section_id:
                resumed = repo.pop_return(
                    db, user_id=user_id, course_id=course_id
                )
                resume_section_id = str(resumed) if resumed else None

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
        reveal=_build_reveal(block),
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
        cause=CauseOut(
            type=cause.type,
            reason=cause.reason,
            blame_concept_id=cause.blame_concept_id,
        ),
        prerequisite=prerequisite_target,
        resume_section_id=resume_section_id,
    )
