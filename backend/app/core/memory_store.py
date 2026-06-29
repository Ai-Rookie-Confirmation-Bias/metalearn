"""프로세스 메모리 저장소 — PERSIST_TO_DB=false 일 때 사용."""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import TypeVar

from app.features.learning.models import LearningItem, LearningSession, TutorStep
from app.features.materials.models import Document, DocumentChunk
from app.features.seed.models import (
    Curriculum,
    DiagnosticAnswer,
    DiagnosticQuestion,
    DiagnosticSession,
    SeedProfile,
)

T = TypeVar("T")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MemoryStore:
    def __init__(self) -> None:
        self.documents: dict[uuid.UUID, Document] = {}
        self.chunks: dict[uuid.UUID, DocumentChunk] = {}
        self.chunks_by_document: dict[uuid.UUID, list[uuid.UUID]] = {}
        self.profiles: dict[uuid.UUID, SeedProfile] = {}
        self.diagnostic_sessions: dict[uuid.UUID, DiagnosticSession] = {}
        self.diagnostic_questions: dict[uuid.UUID, DiagnosticQuestion] = {}
        self.questions_by_session: dict[uuid.UUID, list[uuid.UUID]] = {}
        self.diagnostic_answers: dict[uuid.UUID, DiagnosticAnswer] = {}
        self.curricula: dict[uuid.UUID, Curriculum] = {}
        self.curriculum_by_profile: dict[uuid.UUID, uuid.UUID] = {}
        self.learning_sessions: dict[uuid.UUID, LearningSession] = {}
        self.tutor_steps: dict[uuid.UUID, TutorStep] = {}
        self.steps_by_session: dict[uuid.UUID, list[uuid.UUID]] = {}
        self.learning_items: dict[int, LearningItem] = {}
        self._learning_item_seq = 0

    def clear(self) -> None:
        self.__init__()

    # --- materials ---

    def create_document(self, filename: str, storage_path: str) -> Document:
        doc = Document(
            id=uuid.uuid4(),
            filename=filename,
            storage_path=storage_path,
            page_count=0,
            parse_status="pending",
            skeleton=None,
            created_at=_now(),
        )
        self.documents[doc.id] = doc
        return doc

    def get_document(self, document_id: uuid.UUID) -> Document | None:
        return self.documents.get(document_id)

    def update_document(
        self,
        doc: Document,
        *,
        storage_path: str | None = None,
        page_count: int | None = None,
        parse_status: str | None = None,
        skeleton: dict | None = None,
    ) -> Document:
        if storage_path is not None:
            doc.storage_path = storage_path
        if page_count is not None:
            doc.page_count = page_count
        if parse_status is not None:
            doc.parse_status = parse_status
        if skeleton is not None:
            doc.skeleton = skeleton
        self.documents[doc.id] = doc
        return doc

    def delete_chunks_for_document(self, document_id: uuid.UUID) -> None:
        ids = self.chunks_by_document.pop(document_id, [])
        for cid in ids:
            self.chunks.pop(cid, None)

    def add_chunk(
        self,
        document_id: uuid.UUID,
        page_number: int,
        content: str,
        embedding: list[float] | None = None,
        *,
        concept_id: str | None = None,
    ) -> DocumentChunk:
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=document_id,
            page_number=page_number,
            concept_id=concept_id,
            content=content,
            embedding=embedding,
        )
        self.chunks[chunk.id] = chunk
        self.chunks_by_document.setdefault(document_id, []).append(chunk.id)
        return chunk

    def list_chunks(self, document_id: uuid.UUID) -> list[DocumentChunk]:
        ids = self.chunks_by_document.get(document_id, [])
        chunks = [self.chunks[cid] for cid in ids if cid in self.chunks]
        return sorted(chunks, key=lambda c: c.page_number)

    def get_chunk_by_page(
        self, document_id: uuid.UUID, page_number: int
    ) -> DocumentChunk | None:
        for chunk in self.list_chunks(document_id):
            if chunk.page_number == page_number:
                return chunk
        return None

    def tag_chunk_concept(self, chunk: DocumentChunk, concept_id: str) -> bool:
        if chunk.concept_id is not None:
            return False
        chunk.concept_id = concept_id
        self.chunks[chunk.id] = chunk
        return True

    def search_chunks(
        self,
        document_id: uuid.UUID,
        query_vec: list[float],
        top_k: int,
        concept_id: str | None,
    ) -> list[tuple[DocumentChunk, float]]:
        candidates = self.list_chunks(document_id)
        if concept_id is not None:
            candidates = [c for c in candidates if c.concept_id == concept_id]
        candidates = [c for c in candidates if c.embedding is not None]
        scored: list[tuple[DocumentChunk, float]] = []
        for chunk in candidates:
            score = _cosine_similarity(query_vec, chunk.embedding or [])
            scored.append((chunk, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    # --- seed ---

    def create_profile(
        self,
        document_id: uuid.UUID,
        learning_range: dict,
        learning_goal: str | None,
        concepts_in_range: list[str],
    ) -> SeedProfile:
        profile = SeedProfile(
            id=uuid.uuid4(),
            document_id=document_id,
            learning_range=learning_range,
            learning_goal=learning_goal,
            concepts_in_range=concepts_in_range,
            weaknesses=[],
            status="survey_done",
            created_at=_now(),
        )
        self.profiles[profile.id] = profile
        return profile

    def get_profile(self, profile_id: uuid.UUID) -> SeedProfile | None:
        return self.profiles.get(profile_id)

    def update_profile(
        self,
        profile: SeedProfile,
        *,
        weaknesses: list | None = None,
        status: str | None = None,
    ) -> SeedProfile:
        if weaknesses is not None:
            profile.weaknesses = weaknesses
        if status is not None:
            profile.status = status
        self.profiles[profile.id] = profile
        return profile

    def create_diagnostic_session(self, profile_id: uuid.UUID) -> DiagnosticSession:
        session = DiagnosticSession(
            id=uuid.uuid4(),
            profile_id=profile_id,
            status="in_progress",
            created_at=_now(),
        )
        self.diagnostic_sessions[session.id] = session
        return session

    def get_diagnostic_session(self, session_id: uuid.UUID) -> DiagnosticSession | None:
        return self.diagnostic_sessions.get(session_id)

    def add_question(
        self,
        session_id: uuid.UUID,
        concept_id: str,
        question_text: str,
        options: list[str],
        correct_index: int,
        source_chunk_id: uuid.UUID | None = None,
    ) -> DiagnosticQuestion:
        q = DiagnosticQuestion(
            id=uuid.uuid4(),
            session_id=session_id,
            concept_id=concept_id,
            question_text=question_text,
            options=options,
            correct_index=correct_index,
            source_chunk_id=source_chunk_id,
        )
        self.diagnostic_questions[q.id] = q
        self.questions_by_session.setdefault(session_id, []).append(q.id)
        return q

    def list_questions(self, session_id: uuid.UUID) -> list[DiagnosticQuestion]:
        ids = self.questions_by_session.get(session_id, [])
        return [self.diagnostic_questions[i] for i in ids if i in self.diagnostic_questions]

    def add_answer(
        self, question_id: uuid.UUID, user_choice_index: int, is_correct: bool
    ) -> DiagnosticAnswer:
        ans = DiagnosticAnswer(
            id=uuid.uuid4(),
            question_id=question_id,
            user_choice_index=user_choice_index,
            is_correct=is_correct,
        )
        self.diagnostic_answers[ans.id] = ans
        return ans

    def finish_diagnostic_session(self, session: DiagnosticSession) -> DiagnosticSession:
        session.status = "completed"
        self.diagnostic_sessions[session.id] = session
        return session

    def get_curriculum_by_profile(self, profile_id: uuid.UUID) -> Curriculum | None:
        cid = self.curriculum_by_profile.get(profile_id)
        return self.curricula.get(cid) if cid else None

    def create_curriculum(
        self,
        profile_id: uuid.UUID,
        units: list[dict],
        chapter_groups: list[dict],
        weakness_count: int,
        total_units: int,
    ) -> Curriculum:
        existing = self.get_curriculum_by_profile(profile_id)
        if existing is not None:
            existing.units = units
            existing.chapter_groups = chapter_groups
            existing.weakness_count = weakness_count
            existing.total_units = total_units
            self.curricula[existing.id] = existing
            return existing

        curriculum = Curriculum(
            id=uuid.uuid4(),
            profile_id=profile_id,
            units=units,
            chapter_groups=chapter_groups,
            weakness_count=weakness_count,
            total_units=total_units,
            created_at=_now(),
        )
        self.curricula[curriculum.id] = curriculum
        self.curriculum_by_profile[profile_id] = curriculum.id
        return curriculum

    # --- learning ---

    def create_learning_session(
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
        session = LearningSession(
            id=uuid.uuid4(),
            profile_id=profile_id,
            curriculum_unit_order=curriculum_unit_order,
            concept_id=concept_id,
            status="active",
            session_type=session_type,
            parent_session_id=parent_session_id,
            depth=depth,
            prereq_concept_title=prereq_concept_title,
            created_at=_now(),
            updated_at=_now(),
        )
        self.learning_sessions[session.id] = session
        return session

    def get_learning_session(self, session_id: uuid.UUID) -> LearningSession | None:
        return self.learning_sessions.get(session_id)

    def update_learning_session_status(
        self, session: LearningSession, status: str
    ) -> LearningSession:
        session.status = status
        session.updated_at = _now()
        self.learning_sessions[session.id] = session
        return session

    def touch_learning_session(self, session: LearningSession) -> LearningSession:
        session.updated_at = _now()
        self.learning_sessions[session.id] = session
        return session

    def add_tutor_step(
        self,
        session_id: uuid.UUID,
        step_type: str,
        content: str,
        *,
        user_response: str | None = None,
        is_correct: bool | None = None,
        missing_concept_analysis: dict | None = None,
    ) -> TutorStep:
        step = TutorStep(
            id=uuid.uuid4(),
            session_id=session_id,
            step_type=step_type,
            content=content,
            user_response=user_response,
            is_correct=is_correct,
            missing_concept_analysis=missing_concept_analysis,
            created_at=_now(),
        )
        self.tutor_steps[step.id] = step
        self.steps_by_session.setdefault(session_id, []).append(step.id)
        return step

    def update_tutor_step_response(
        self, step: TutorStep, user_response: str, is_correct: bool
    ) -> TutorStep:
        step.user_response = user_response
        step.is_correct = is_correct
        self.tutor_steps[step.id] = step
        return step

    def list_tutor_steps(self, session_id: uuid.UUID) -> list[TutorStep]:
        ids = self.steps_by_session.get(session_id, [])
        steps = [self.tutor_steps[i] for i in ids if i in self.tutor_steps]
        return sorted(steps, key=lambda s: s.created_at)

    def get_tutor_step_by_type(
        self, session_id: uuid.UUID, step_type: str
    ) -> TutorStep | None:
        for step in self.list_tutor_steps(session_id):
            if step.step_type == step_type:
                return step
        return None

    def add_learning_item(
        self, content: str, embedding: list[float] | None = None
    ) -> LearningItem:
        self._learning_item_seq += 1
        item = LearningItem(
            id=self._learning_item_seq,
            content=content,
            embedding=embedding,
            created_at=_now(),
        )
        self.learning_items[item.id] = item
        return item


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


_store = MemoryStore()


def get_memory_store() -> MemoryStore:
    return _store
