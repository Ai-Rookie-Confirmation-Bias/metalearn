"""[4.Repository] 진단 세션/숙련도/문항 DB 입출력.

병합 2단계(UUID 포팅):
- Enrollment/ConceptMastery는 정본(features/learning/models.py)을 사용.
- 숙련도는 사용자×개념 단일 테이블(concept_mastery)에 세션 작업 상태
  (session_id/answered_count/resolved/locked)를 얹어 기록 — 세션 재시작 시
  같은 (user, concept) 행을 재사용(업서트)한다.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.features.diagnostic.models import DiagnosticQuestion, DiagnosticSession
from app.features.learning.models import ConceptMastery, Enrollment
from app.features.materials.models import DocChunk
from app.features.seed.models import Concept, ConceptEdge, Course


class DiagnosticRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── 원문 근거 (RAG 주입) ──────────────────────────────────
    def get_chunk_contents(self, chunk_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        """doc_chunks 원문 조회 — 문항 생성 프롬프트에 근거로 주입."""
        if not chunk_ids:
            return {}
        rows = self.db.scalars(
            select(DocChunk).where(DocChunk.id.in_(chunk_ids))
        ).all()
        return {row.id: row.content for row in rows}

    # ── Enrollment ────────────────────────────────────────────
    def ensure_enrollment(
        self, *, user_id: uuid.UUID, course_id: uuid.UUID
    ) -> Enrollment:
        enrollment = self.db.get(Enrollment, (user_id, course_id))
        if enrollment is None:
            enrollment = Enrollment(user_id=user_id, course_id=course_id)
            self.db.add(enrollment)
            self.db.flush()
        return enrollment

    def set_enrollment_diag_status(
        self, *, user_id: uuid.UUID, course_id: uuid.UUID, status: str
    ) -> None:
        enrollment = self.ensure_enrollment(user_id=user_id, course_id=course_id)
        enrollment.diag_status = status
        self.db.flush()

    def increment_diag_q_count(
        self, *, user_id: uuid.UUID, course_id: uuid.UUID
    ) -> None:
        enrollment = self.ensure_enrollment(user_id=user_id, course_id=course_id)
        enrollment.diag_q_count += 1
        self.db.flush()

    # ── Session ───────────────────────────────────────────────
    def get_course(self, course_id: uuid.UUID) -> Course | None:
        return self.db.get(Course, course_id)

    def create_session(self, *, course_id: uuid.UUID) -> DiagnosticSession:
        session = DiagnosticSession(course_id=course_id, status="active")
        self.db.add(session)
        self.db.flush()
        return session

    def get_session(self, session_id: uuid.UUID) -> DiagnosticSession | None:
        return self.db.get(DiagnosticSession, session_id)

    def complete_session(self, session: DiagnosticSession) -> None:
        session.status = "completed"
        session.completed_at = datetime.now(timezone.utc)
        course = self.get_course(session.course_id)
        if course is not None:
            self.set_enrollment_diag_status(
                user_id=course.user_id,
                course_id=course.id,
                status="completed",
            )
        self.db.flush()

    # ── Concept ───────────────────────────────────────────────
    def list_concepts(self, course_id: uuid.UUID) -> list[Concept]:
        # UUID 포팅 주: 생성순 근사(created_at) + id 타이브레이크로 결정적 순서 보장.
        stmt = (
            select(Concept)
            .where(Concept.course_id == course_id)
            .order_by(Concept.created_at, Concept.id)
        )
        return list(self.db.scalars(stmt))

    def get_prerequisite_ids(self, concept_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = select(ConceptEdge.to_concept_id).where(
            ConceptEdge.from_concept_id == concept_id,
            ConceptEdge.kind == "prerequisite",
        )
        return list(self.db.scalars(stmt))

    def get_dependent_ids(self, concept_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = select(ConceptEdge.from_concept_id).where(
            ConceptEdge.to_concept_id == concept_id,
            ConceptEdge.kind == "prerequisite",
        )
        return list(self.db.scalars(stmt))

    def get_all_prerequisite_target_ids(
        self, concept_ids: list[uuid.UUID]
    ) -> set[uuid.UUID]:
        if not concept_ids:
            return set()
        stmt = select(ConceptEdge.to_concept_id).where(
            ConceptEdge.from_concept_id.in_(concept_ids),
            ConceptEdge.kind == "prerequisite",
        )
        return set(self.db.scalars(stmt))

    def get_all_sub_ids(self, concept_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        """선수(prerequisite)이거나 섹션 하위(contains)인 개념 전부 — 진단 시작 시 잠금 대상."""
        if not concept_ids:
            return set()
        stmt = select(ConceptEdge.to_concept_id).where(
            ConceptEdge.from_concept_id.in_(concept_ids),
            ConceptEdge.kind.in_(["prerequisite", "contains"]),
        )
        return set(self.db.scalars(stmt))

    def get_contains_child_ids(self, concept_id: uuid.UUID) -> list[uuid.UUID]:
        """섹션 노드의 하위(contains) 개념 id — id 순 (오답 시 대표 샘플 출제용)."""
        stmt = (
            select(ConceptEdge.to_concept_id)
            .where(
                ConceptEdge.from_concept_id == concept_id,
                ConceptEdge.kind == "contains",
            )
            .order_by(ConceptEdge.to_concept_id)
        )
        return list(self.db.scalars(stmt))

    def get_container_ids(self, concept_id: uuid.UUID) -> list[uuid.UUID]:
        """이 개념을 하위로 갖는 섹션 노드 id."""
        stmt = select(ConceptEdge.from_concept_id).where(
            ConceptEdge.to_concept_id == concept_id,
            ConceptEdge.kind == "contains",
        )
        return list(self.db.scalars(stmt))

    # ── Mastery ───────────────────────────────────────────────
    def create_masteries(
        self,
        *,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        concept_ids: list[uuid.UUID],
        strength_init: float,
        locked_ids: set[uuid.UUID] | None = None,
    ) -> None:
        """세션 시작 시 사용자×개념 숙련도 행을 업서트한다.

        UUID 포팅 주: 정본 concept_mastery의 PK는 (user_id, concept_id) —
        세션별 새 행이 아니라 같은 행에 세션 작업 상태를 리셋해 재사용한다
        (진단 재시작 시 strength/answered_count/resolved/locked 초기화).
        """
        locked_ids = locked_ids or set()
        if not concept_ids:
            return
        stmt = pg_insert(ConceptMastery).values(
            [
                {
                    "user_id": user_id,
                    "concept_id": cid,
                    "session_id": session_id,
                    "strength": strength_init,
                    "answered_count": 0,
                    "resolved": False,
                    "locked": cid in locked_ids,
                }
                for cid in concept_ids
            ]
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "concept_id"],
            set_={
                "session_id": stmt.excluded.session_id,
                "strength": stmt.excluded.strength,
                "answered_count": stmt.excluded.answered_count,
                "resolved": stmt.excluded.resolved,
                "locked": stmt.excluded.locked,
            },
        )
        self.db.execute(stmt)
        # ORM 캐시와 벌크 업서트 정합: 이후 조회가 낡은 객체를 보지 않도록 만료.
        self.db.expire_all()
        self.db.flush()

    def list_masteries(self, session_id: uuid.UUID) -> list[ConceptMastery]:
        stmt = select(ConceptMastery).where(ConceptMastery.session_id == session_id)
        return list(self.db.scalars(stmt))

    def get_mastery(
        self, *, session_id: uuid.UUID, concept_id: uuid.UUID
    ) -> ConceptMastery | None:
        stmt = select(ConceptMastery).where(
            ConceptMastery.session_id == session_id,
            ConceptMastery.concept_id == concept_id,
        )
        return self.db.scalars(stmt).first()

    def unlock_mastery(self, *, session_id: uuid.UUID, concept_id: uuid.UUID) -> None:
        m = self.get_mastery(session_id=session_id, concept_id=concept_id)
        if m is not None and m.locked:
            m.locked = False
            self.db.flush()

    # ── Question ──────────────────────────────────────────────
    def create_question(
        self,
        *,
        session_id: uuid.UUID,
        concept_id: uuid.UUID,
        qtype: str,
        question: str,
        explanation: str,
        options: list[str] | None = None,
        answer_index: int | None = None,
        expected_answer: str | None = None,
        acceptable_answers: list[str] | None = None,
        is_active: bool = False,
    ) -> DiagnosticQuestion:
        q = DiagnosticQuestion(
            session_id=session_id,
            concept_id=concept_id,
            qtype=qtype,
            question=question,
            explanation=explanation,
            options=options,
            answer_index=answer_index,
            expected_answer=expected_answer,
            acceptable_answers=acceptable_answers,
            is_active=is_active,
        )
        self.db.add(q)
        self.db.flush()
        return q

    def get_question(self, question_id: uuid.UUID) -> DiagnosticQuestion | None:
        return self.db.get(DiagnosticQuestion, question_id)

    def get_active_question(self, session_id: uuid.UUID) -> DiagnosticQuestion | None:
        stmt = (
            select(DiagnosticQuestion)
            .where(
                DiagnosticQuestion.session_id == session_id,
                DiagnosticQuestion.is_active.is_(True),
                DiagnosticQuestion.answered.is_(False),
            )
            # UUID 포팅 주: 생성순 근사는 created_at, id는 결정성 타이브레이크.
            .order_by(
                DiagnosticQuestion.created_at.desc(), DiagnosticQuestion.id.desc()
            )
        )
        return self.db.scalars(stmt).first()

    def get_pool_question(
        self, *, session_id: uuid.UUID, concept_id: uuid.UUID
    ) -> DiagnosticQuestion | None:
        stmt = (
            select(DiagnosticQuestion)
            .where(
                DiagnosticQuestion.session_id == session_id,
                DiagnosticQuestion.concept_id == concept_id,
                DiagnosticQuestion.is_active.is_(False),
                DiagnosticQuestion.answered.is_(False),
            )
            .order_by(DiagnosticQuestion.created_at, DiagnosticQuestion.id)
        )
        return self.db.scalars(stmt).first()

    def has_questions_for_concept(
        self, session_id: uuid.UUID, concept_id: uuid.UUID
    ) -> bool:
        stmt = (
            select(DiagnosticQuestion.id)
            .where(
                DiagnosticQuestion.session_id == session_id,
                DiagnosticQuestion.concept_id == concept_id,
            )
            .limit(1)
        )
        return self.db.scalars(stmt).first() is not None

    def get_sole_unanswered(self, session_id: uuid.UUID) -> DiagnosticQuestion | None:
        stmt = select(DiagnosticQuestion).where(
            DiagnosticQuestion.session_id == session_id,
            DiagnosticQuestion.answered.is_(False),
        )
        rows = list(self.db.scalars(stmt))
        return rows[0] if len(rows) == 1 else None

    def count_answered_questions(self, session_id: uuid.UUID) -> int:
        stmt = select(func.count(DiagnosticQuestion.id)).where(
            DiagnosticQuestion.session_id == session_id,
            DiagnosticQuestion.answered.is_(True),
        )
        return int(self.db.scalar(stmt) or 0)
