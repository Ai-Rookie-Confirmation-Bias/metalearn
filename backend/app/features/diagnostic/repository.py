"""[4.Repository] 진단 세션/숙련도/문항 DB 입출력.

트랜잭션 commit은 서비스가 담당. 여기서는 flush까지만.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.diagnostic.models import (
    ConceptMastery,
    DiagnosticQuestion,
    DiagnosticSession,
)
from app.features.materials.models import Concept, ConceptPrerequisite


class DiagnosticRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Session ───────────────────────────────────────────────
    def create_session(self, *, material_id: int) -> DiagnosticSession:
        session = DiagnosticSession(material_id=material_id, status="active")
        self.db.add(session)
        self.db.flush()
        return session

    def get_session(self, session_id: int) -> DiagnosticSession | None:
        return self.db.get(DiagnosticSession, session_id)

    def complete_session(self, session: DiagnosticSession) -> None:
        session.status = "completed"
        session.completed_at = datetime.now(timezone.utc)
        self.db.flush()

    # ── Concept (materials 도메인 조회) ───────────────────────
    def list_concepts(self, material_id: int) -> list[Concept]:
        stmt = select(Concept).where(Concept.material_id == material_id).order_by(Concept.id)
        return list(self.db.scalars(stmt))

    # ── 그래프 조회 ───────────────────────────────────────────────
    def get_prerequisite_ids(self, concept_id: int) -> list[int]:
        """concept_id가 직접 의존하는 선수 개념 ID 목록."""
        stmt = select(ConceptPrerequisite.prerequisite_concept_id).where(
            ConceptPrerequisite.concept_id == concept_id
        )
        return list(self.db.scalars(stmt))

    def get_dependent_ids(self, concept_id: int) -> list[int]:
        """concept_id를 선수로 갖는 후속 개념 ID 목록."""
        stmt = select(ConceptPrerequisite.concept_id).where(
            ConceptPrerequisite.prerequisite_concept_id == concept_id
        )
        return list(self.db.scalars(stmt))

    def get_all_prerequisite_target_ids(self, concept_ids: list[int]) -> set[int]:
        """주어진 개념들 중 '누군가의 선수지식'으로 쓰이는 개념 ID 집합.

        이 집합에 없는 개념 = 최상위(메인) 개념.
        """
        if not concept_ids:
            return set()
        stmt = select(ConceptPrerequisite.prerequisite_concept_id).where(
            ConceptPrerequisite.concept_id.in_(concept_ids)
        )
        return set(self.db.scalars(stmt))

    # ── Mastery ───────────────────────────────────────────────
    def create_masteries(
        self,
        *,
        session_id: int,
        concept_ids: list[int],
        p_init: float,
        locked_ids: set[int] | None = None,
    ) -> None:
        locked_ids = locked_ids or set()
        self.db.add_all(
            ConceptMastery(
                session_id=session_id,
                concept_id=cid,
                p_known=p_init,
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
        """현재 출제 중(활성)이며 아직 미응답인 문항."""
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
        """풀에서 해당 개념의 다음 미사용 문항."""
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

    def has_question_pool(self, session_id: int) -> bool:
        stmt = select(DiagnosticQuestion.id).where(
            DiagnosticQuestion.session_id == session_id
        )
        return self.db.scalars(stmt).first() is not None

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
        """미응답 문항이 정확히 1개일 때만 반환 (레거시/마지막 문항)."""
        stmt = select(DiagnosticQuestion).where(
            DiagnosticQuestion.session_id == session_id,
            DiagnosticQuestion.answered.is_(False),
        )
        rows = list(self.db.scalars(stmt))
        return rows[0] if len(rows) == 1 else None

    def get_open_question(self, session_id: int) -> DiagnosticQuestion | None:
        """하위 호환: 활성 문항 우선, 없으면 기존 방식."""
        active = self.get_active_question(session_id)
        if active is not None:
            return active
        stmt = (
            select(DiagnosticQuestion)
            .where(
                DiagnosticQuestion.session_id == session_id,
                DiagnosticQuestion.answered.is_(False),
            )
            .order_by(DiagnosticQuestion.id.desc())
        )
        return self.db.scalars(stmt).first()
