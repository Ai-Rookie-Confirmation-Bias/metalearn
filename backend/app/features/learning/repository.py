"""[4.Repository] 학습 세션·튜터 스텝 DB 접근."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.memory_store import get_memory_store
from app.features.learning.models import LearningItem, LearningSession, TutorStep


class LearningRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._mem = get_memory_store()

    def add(self, content: str, embedding: list[float] | None = None) -> LearningItem:
        if not settings.PERSIST_TO_DB:
            return self._mem.add_learning_item(content, embedding)
        item = LearningItem(content=content, embedding=embedding)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def search_similar(self, embedding: list[float], limit: int = 5) -> list[LearningItem]:
        if not settings.PERSIST_TO_DB:
            return []
        stmt = (
            select(LearningItem)
            .order_by(LearningItem.embedding.cosine_distance(embedding))
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def create_session(
        self,
        profile_id: uuid.UUID,
        curriculum_unit_order: int,
        concept_id: str,
        *,
        session_type: str = "pdf_concept",
        parent_session_id: uuid.UUID | None = None,
        depth: int = 0,
        prereq_concept_title: str | None = None,
    ) -> LearningSession:
        if not settings.PERSIST_TO_DB:
            return self._mem.create_learning_session(
                profile_id,
                curriculum_unit_order,
                concept_id,
                session_type=session_type,
                parent_session_id=parent_session_id,
                depth=depth,
                prereq_concept_title=prereq_concept_title,
            )
        session = LearningSession(
            profile_id=profile_id,
            curriculum_unit_order=curriculum_unit_order,
            concept_id=concept_id,
            status="active",
            session_type=session_type,
            parent_session_id=parent_session_id,
            depth=depth,
            prereq_concept_title=prereq_concept_title,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: uuid.UUID) -> LearningSession | None:
        if not settings.PERSIST_TO_DB:
            return self._mem.get_learning_session(session_id)
        return self.db.get(LearningSession, session_id)

    def update_session_status(self, session: LearningSession, status: str) -> LearningSession:
        if not settings.PERSIST_TO_DB:
            return self._mem.update_learning_session_status(session, status)
        session.status = status
        self.db.commit()
        self.db.refresh(session)
        return session

    def touch_session(self, session: LearningSession) -> LearningSession:
        if not settings.PERSIST_TO_DB:
            return self._mem.touch_learning_session(session)
        from datetime import datetime, timezone

        session.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(session)
        return session

    def add_step(
        self,
        session_id: uuid.UUID,
        step_type: str,
        content: str,
        *,
        user_response: str | None = None,
        is_correct: bool | None = None,
        missing_concept_analysis: dict | None = None,
    ) -> TutorStep:
        if not settings.PERSIST_TO_DB:
            return self._mem.add_tutor_step(
                session_id,
                step_type,
                content,
                user_response=user_response,
                is_correct=is_correct,
                missing_concept_analysis=missing_concept_analysis,
            )
        step = TutorStep(
            session_id=session_id,
            step_type=step_type,
            content=content,
            user_response=user_response,
            is_correct=is_correct,
            missing_concept_analysis=missing_concept_analysis,
        )
        self.db.add(step)
        self.db.commit()
        self.db.refresh(step)
        return step

    def update_step_response(
        self,
        step: TutorStep,
        user_response: str,
        is_correct: bool,
    ) -> TutorStep:
        if not settings.PERSIST_TO_DB:
            return self._mem.update_tutor_step_response(step, user_response, is_correct)
        step.user_response = user_response
        step.is_correct = is_correct
        self.db.commit()
        self.db.refresh(step)
        return step

    def list_steps(self, session_id: uuid.UUID) -> list[TutorStep]:
        if not settings.PERSIST_TO_DB:
            return self._mem.list_tutor_steps(session_id)
        stmt = (
            select(TutorStep)
            .where(TutorStep.session_id == session_id)
            .order_by(TutorStep.created_at)
        )
        return list(self.db.scalars(stmt))

    def get_step_by_type(self, session_id: uuid.UUID, step_type: str) -> TutorStep | None:
        if not settings.PERSIST_TO_DB:
            return self._mem.get_tutor_step_by_type(session_id, step_type)
        stmt = (
            select(TutorStep)
            .where(TutorStep.session_id == session_id, TutorStep.step_type == step_type)
            .order_by(TutorStep.created_at)
            .limit(1)
        )
        return self.db.scalars(stmt).first()
