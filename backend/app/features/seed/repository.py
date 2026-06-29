"""[4.Repository] seed 프로필·진단 DB 접근."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.memory_store import get_memory_store
from app.features.seed.models import (
    Curriculum,
    DiagnosticAnswer,
    DiagnosticQuestion,
    DiagnosticSession,
    SeedProfile,
)


class SeedRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._mem = get_memory_store()

    def create_profile(
        self,
        document_id: uuid.UUID,
        learning_range: dict,
        learning_goal: str | None,
        concepts_in_range: list[str],
    ) -> SeedProfile:
        if not settings.PERSIST_TO_DB:
            return self._mem.create_profile(
                document_id, learning_range, learning_goal, concepts_in_range
            )
        profile = SeedProfile(
            document_id=document_id,
            learning_range=learning_range,
            learning_goal=learning_goal,
            concepts_in_range=concepts_in_range,
        )
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def get_profile(self, profile_id: uuid.UUID) -> SeedProfile | None:
        if not settings.PERSIST_TO_DB:
            return self._mem.get_profile(profile_id)
        return self.db.get(SeedProfile, profile_id)

    def update_profile(
        self,
        profile: SeedProfile,
        *,
        weaknesses: list | None = None,
        status: str | None = None,
    ) -> SeedProfile:
        if not settings.PERSIST_TO_DB:
            return self._mem.update_profile(profile, weaknesses=weaknesses, status=status)
        if weaknesses is not None:
            profile.weaknesses = weaknesses
        if status is not None:
            profile.status = status
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def create_session(self, profile_id: uuid.UUID) -> DiagnosticSession:
        if not settings.PERSIST_TO_DB:
            return self._mem.create_diagnostic_session(profile_id)
        session = DiagnosticSession(profile_id=profile_id)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: uuid.UUID) -> DiagnosticSession | None:
        if not settings.PERSIST_TO_DB:
            return self._mem.get_diagnostic_session(session_id)
        return self.db.get(DiagnosticSession, session_id)

    def add_question(
        self,
        session_id: uuid.UUID,
        concept_id: str,
        question_text: str,
        options: list[str],
        correct_index: int,
        source_chunk_id: uuid.UUID | None = None,
    ) -> DiagnosticQuestion:
        if not settings.PERSIST_TO_DB:
            return self._mem.add_question(
                session_id,
                concept_id,
                question_text,
                options,
                correct_index,
                source_chunk_id,
            )
        q = DiagnosticQuestion(
            session_id=session_id,
            concept_id=concept_id,
            question_text=question_text,
            options=options,
            correct_index=correct_index,
            source_chunk_id=source_chunk_id,
        )
        self.db.add(q)
        self.db.commit()
        self.db.refresh(q)
        return q

    def list_questions(self, session_id: uuid.UUID) -> list[DiagnosticQuestion]:
        if not settings.PERSIST_TO_DB:
            return self._mem.list_questions(session_id)
        stmt = select(DiagnosticQuestion).where(DiagnosticQuestion.session_id == session_id)
        return list(self.db.scalars(stmt))

    def add_answer(
        self, question_id: uuid.UUID, user_choice_index: int, is_correct: bool
    ) -> DiagnosticAnswer:
        if not settings.PERSIST_TO_DB:
            return self._mem.add_answer(question_id, user_choice_index, is_correct)
        ans = DiagnosticAnswer(
            question_id=question_id,
            user_choice_index=user_choice_index,
            is_correct=is_correct,
        )
        self.db.add(ans)
        self.db.commit()
        self.db.refresh(ans)
        return ans

    def finish_session(self, session: DiagnosticSession) -> DiagnosticSession:
        if not settings.PERSIST_TO_DB:
            return self._mem.finish_diagnostic_session(session)
        session.status = "completed"
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_curriculum_by_profile(self, profile_id: uuid.UUID) -> Curriculum | None:
        if not settings.PERSIST_TO_DB:
            return self._mem.get_curriculum_by_profile(profile_id)
        stmt = select(Curriculum).where(Curriculum.profile_id == profile_id)
        return self.db.scalars(stmt).first()

    def create_curriculum(
        self,
        profile_id: uuid.UUID,
        units: list[dict],
        chapter_groups: list[dict],
        weakness_count: int,
        total_units: int,
    ) -> Curriculum:
        if not settings.PERSIST_TO_DB:
            return self._mem.create_curriculum(
                profile_id, units, chapter_groups, weakness_count, total_units
            )
        existing = self.get_curriculum_by_profile(profile_id)
        if existing is not None:
            existing.units = units
            existing.chapter_groups = chapter_groups
            existing.weakness_count = weakness_count
            existing.total_units = total_units
            self.db.commit()
            self.db.refresh(existing)
            return existing

        curriculum = Curriculum(
            profile_id=profile_id,
            units=units,
            chapter_groups=chapter_groups,
            weakness_count=weakness_count,
            total_units=total_units,
        )
        self.db.add(curriculum)
        self.db.commit()
        self.db.refresh(curriculum)
        return curriculum
