"""[4.Repository] 진단 세션/숙련도/문항 DB 입출력."""
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.features.diagnostic.models import (
    ConceptMastery,
    DiagnosticQuestion,
    DiagnosticSession,
    Enrollment,
)
from app.features.documents.models import Concept, ConceptEdge, Course


class DiagnosticRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Enrollment ────────────────────────────────────────────
    def ensure_enrollment(self, *, user_id: int, course_id: int) -> Enrollment:
        enrollment = self.db.get(Enrollment, (user_id, course_id))
        if enrollment is None:
            enrollment = Enrollment(user_id=user_id, course_id=course_id)
            self.db.add(enrollment)
            self.db.flush()
        return enrollment

    def set_enrollment_diag_status(
        self, *, user_id: int, course_id: int, status: str
    ) -> None:
        enrollment = self.ensure_enrollment(user_id=user_id, course_id=course_id)
        enrollment.diag_status = status
        self.db.flush()

    def increment_diag_q_count(self, *, user_id: int, course_id: int) -> None:
        enrollment = self.ensure_enrollment(user_id=user_id, course_id=course_id)
        enrollment.diag_q_count += 1
        self.db.flush()

    # ── Session ───────────────────────────────────────────────
    def get_course(self, course_id: int) -> Course | None:
        return self.db.get(Course, course_id)

    def create_session(self, *, course_id: int) -> DiagnosticSession:
        session = DiagnosticSession(course_id=course_id, status="active")
        self.db.add(session)
        self.db.flush()
        return session

    def get_session(self, session_id: int) -> DiagnosticSession | None:
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
    def list_concepts(self, course_id: int) -> list[Concept]:
        stmt = select(Concept).where(Concept.course_id == course_id).order_by(Concept.id)
        return list(self.db.scalars(stmt))

    def get_prerequisite_ids(self, concept_id: int) -> list[int]:
        stmt = select(ConceptEdge.to_concept_id).where(
            ConceptEdge.from_concept_id == concept_id,
            ConceptEdge.kind == "prerequisite",
        )
        return list(self.db.scalars(stmt))

    def get_dependent_ids(self, concept_id: int) -> list[int]:
        stmt = select(ConceptEdge.from_concept_id).where(
            ConceptEdge.to_concept_id == concept_id,
            ConceptEdge.kind == "prerequisite",
        )
        return list(self.db.scalars(stmt))

    def get_all_prerequisite_target_ids(self, concept_ids: list[int]) -> set[int]:
        if not concept_ids:
            return set()
        stmt = select(ConceptEdge.to_concept_id).where(
            ConceptEdge.from_concept_id.in_(concept_ids),
            ConceptEdge.kind == "prerequisite",
        )
        return set(self.db.scalars(stmt))

    def get_all_sub_ids(self, concept_ids: list[int]) -> set[int]:
        """선수(prerequisite)이거나 섹션 하위(contains)인 개념 전부 — 진단 시작 시 잠금 대상."""
        if not concept_ids:
            return set()
        stmt = select(ConceptEdge.to_concept_id).where(
            ConceptEdge.from_concept_id.in_(concept_ids),
            ConceptEdge.kind.in_(["prerequisite", "contains"]),
        )
        return set(self.db.scalars(stmt))

    def get_contains_child_ids(self, concept_id: int) -> list[int]:
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

    def get_container_ids(self, concept_id: int) -> list[int]:
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
        session_id: int,
        concept_ids: list[int],
        strength_init: float,
        locked_ids: set[int] | None = None,
    ) -> None:
        locked_ids = locked_ids or set()
        self.db.add_all(
            ConceptMastery(
                session_id=session_id,
                concept_id=cid,
                strength=strength_init,
                locked=cid in locked_ids,
            )
            for cid in concept_ids
        )
        self.db.flush()

    def list_masteries(self, session_id: int) -> list[ConceptMastery]:
        stmt = select(ConceptMastery).where(ConceptMastery.session_id == session_id)
        return list(self.db.scalars(stmt))

    def get_mastery(self, *, session_id: int, concept_id: int) -> ConceptMastery | None:
        stmt = select(ConceptMastery).where(
            ConceptMastery.session_id == session_id,
            ConceptMastery.concept_id == concept_id,
        )
        return self.db.scalars(stmt).first()

    def unlock_mastery(self, *, session_id: int, concept_id: int) -> None:
        m = self.get_mastery(session_id=session_id, concept_id=concept_id)
        if m is not None and m.locked:
            m.locked = False
            self.db.flush()

    # ── Question ──────────────────────────────────────────────
    def create_question(
        self,
        *,
        session_id: int,
        concept_id: int,
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

    def get_question(self, question_id: int) -> DiagnosticQuestion | None:
        return self.db.get(DiagnosticQuestion, question_id)

    def get_active_question(self, session_id: int) -> DiagnosticQuestion | None:
        stmt = (
            select(DiagnosticQuestion)
            .where(
                DiagnosticQuestion.session_id == session_id,
                DiagnosticQuestion.is_active.is_(True),
                DiagnosticQuestion.answered.is_(False),
            )
            .order_by(DiagnosticQuestion.id.desc())
        )
        return self.db.scalars(stmt).first()

    def get_pool_question(
        self, *, session_id: int, concept_id: int
    ) -> DiagnosticQuestion | None:
        stmt = (
            select(DiagnosticQuestion)
            .where(
                DiagnosticQuestion.session_id == session_id,
                DiagnosticQuestion.concept_id == concept_id,
                DiagnosticQuestion.is_active.is_(False),
                DiagnosticQuestion.answered.is_(False),
            )
            .order_by(DiagnosticQuestion.id)
        )
        return self.db.scalars(stmt).first()

    def has_questions_for_concept(self, session_id: int, concept_id: int) -> bool:
        stmt = (
            select(DiagnosticQuestion.id)
            .where(
                DiagnosticQuestion.session_id == session_id,
                DiagnosticQuestion.concept_id == concept_id,
            )
            .limit(1)
        )
        return self.db.scalars(stmt).first() is not None

    def get_sole_unanswered(self, session_id: int) -> DiagnosticQuestion | None:
        stmt = select(DiagnosticQuestion).where(
            DiagnosticQuestion.session_id == session_id,
            DiagnosticQuestion.answered.is_(False),
        )
        rows = list(self.db.scalars(stmt))
        return rows[0] if len(rows) == 1 else None

    def count_answered_questions(self, session_id: int) -> int:
        stmt = select(func.count(DiagnosticQuestion.id)).where(
            DiagnosticQuestion.session_id == session_id,
            DiagnosticQuestion.answered.is_(True),
        )
        return int(self.db.scalar(stmt) or 0)
