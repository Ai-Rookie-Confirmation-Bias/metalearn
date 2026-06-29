"""[3.Service] 학습 생성 + 튜터 세션."""
from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.llm.factory import get_llm_client
from app.core.vector_store import ChunkResult, search_similar_chunks
from app.features.learning.models import LearningSession
from app.features.learning.repository import LearningRepository
from app.features.learning.schemas import (
    CompleteSessionResponse,
    GenerateRequest,
    GenerateResponse,
    HintResponse,
    RespondCorrectResponse,
    RespondIncorrectResponse,
    StartPrerequisiteResponse,
    StartSessionRequest,
    StartSessionResponse,
    WeaknessEntry,
)
from app.features.learning.tutor import (
    generate_answer_reveal,
    generate_hint_1,
    generate_hint_2,
    generate_prereq_answer_reveal,
    generate_prereq_question,
    generate_question,
    infer_missing_concept,
    infer_prerequisite_concept,
    judge_response,
)
from app.features.materials.repository import MaterialsRepository
from app.features.seed.repository import SeedRepository
from app.features.seed.schemas import CurriculumUnit
from app.features.seed.weakness_utils import (
    normalize_weakness_entry,
    normalize_weaknesses,
    remove_weakness,
    upsert_weakness,
)


def update_weakness_after_session(session_id: uuid.UUID, db: Session) -> CompleteSessionResponse:
    """세션 결과에 따라 seed_profiles.weaknesses를 갱신한다."""
    repo = LearningRepository(db)
    seed = SeedRepository(db)

    session = repo.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="학습 세션을 찾을 수 없습니다.")
    if session.status == "completed":
        raise HTTPException(status_code=409, detail="아직 답변이 제출되지 않았습니다.")

    question_step = repo.get_step_by_type(session_id, "question")
    if question_step is None or question_step.is_correct is None:
        raise HTTPException(status_code=409, detail="아직 답변이 제출되지 않았습니다.")

    profile = seed.get_profile(session.profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Seed 프로필을 찾을 수 없습니다.")

    concept_id = session.concept_id
    weaknesses = list(profile.weaknesses or [])
    is_correct = bool(question_step.is_correct)
    reached_answer_reveal = repo.get_step_by_type(session_id, "answer_reveal") is not None

    if is_correct:
        weaknesses = remove_weakness(weaknesses, concept_id)
        resolved = True
    elif reached_answer_reveal:
        hint_1 = repo.get_step_by_type(session_id, "hint_1")
        analysis = hint_1.missing_concept_analysis if hint_1 else None
        if analysis:
            entry = {
                "concept_id": concept_id,
                "missing_concept": str(analysis.get("missing_concept") or concept_id),
                "reason": str(analysis.get("reason") or ""),
            }
        else:
            entry = normalize_weakness_entry(concept_id)
        weaknesses = upsert_weakness(weaknesses, entry)
        resolved = False
    else:
        resolved = False

    profile.weaknesses = normalize_weaknesses(weaknesses)
    from app.core.config import settings
    from app.core.memory_store import get_memory_store
    if settings.PERSIST_TO_DB:
        db.commit()
        db.refresh(profile)
    else:
        get_memory_store().profiles[profile.id] = profile

    return CompleteSessionResponse(
        concept_id=concept_id,
        resolved=resolved,
        current_weaknesses=[
            WeaknessEntry(**w) if isinstance(w, dict) else WeaknessEntry(concept_id=str(w))
            for w in normalize_weaknesses(profile.weaknesses or [])
        ],
    )


class LearningService:
    def __init__(self, db: Session) -> None:
        self.repo = LearningRepository(db)
        self.seed = SeedRepository(db)
        self.materials = MaterialsRepository(db)
        self.db = db

    async def generate(self, req: GenerateRequest) -> GenerateResponse:
        llm = get_llm_client()
        content = await llm.generate(
            f"다음 주제로 학습 항목을 만들어줘 (한국어, 3~5문장): {req.topic}"
        )
        self.repo.add(content=content)
        return GenerateResponse(content=content)

    def _get_unit(self, profile_id: uuid.UUID, unit_order: int) -> tuple[CurriculumUnit, uuid.UUID]:
        profile = self.seed.get_profile(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Seed 프로필을 찾을 수 없습니다.")

        curriculum = self.seed.get_curriculum_by_profile(profile_id)
        if curriculum is None:
            raise HTTPException(status_code=404, detail="커리큘럼이 없습니다. 먼저 생성해 주세요.")

        for raw in curriculum.units:
            if raw.get("order") == unit_order:
                unit = CurriculumUnit.model_validate(raw)
                return unit, profile.document_id

        raise HTTPException(
            status_code=404,
            detail=f"unit_order={unit_order} 에 해당하는 단원이 없습니다.",
        )

    def _chunks_from_unit(self, document_id: uuid.UUID, unit: CurriculumUnit) -> list[ChunkResult]:
        if not unit.chunk_ids:
            return []
        id_set = {str(cid) for cid in unit.chunk_ids}
        results: list[ChunkResult] = []
        for ch in self.materials.list_chunks(document_id):
            if str(ch.id) in id_set and ch.content.strip():
                results.append(
                    ChunkResult(
                        chunk_id=ch.id,
                        page_number=ch.page_number,
                        text=ch.content,
                        similarity_score=1.0,
                    )
                )
        return results[:3]

    async def _fetch_chunks(
        self, document_id: uuid.UUID, unit: CurriculumUnit
    ) -> list[ChunkResult]:
        query = f"{unit.title} {unit.focus or ''}".strip()
        chunks = await search_similar_chunks(
            query=query,
            document_id=str(document_id),
            top_k=3,
            concept_id=unit.concept_id,
        )
        if chunks:
            return chunks
        return self._chunks_from_unit(document_id, unit)

    async def _get_session_context(
        self, session: LearningSession
    ) -> tuple[str, str | None, list[ChunkResult], str | None]:
        """(title, focus, chunks, unit_content) 반환. prerequisite 세션은 chunks=[]."""
        if getattr(session, "session_type", "pdf_concept") == "prerequisite":
            title = getattr(session, "prereq_concept_title", None) or session.concept_id
            return title, None, [], None

        unit, document_id = self._get_unit(session.profile_id, session.curriculum_unit_order)
        chunks = await self._fetch_chunks(document_id, unit)
        return unit.title, unit.focus, chunks, unit.content

    async def start_session(self, req: StartSessionRequest) -> StartSessionResponse:
        unit, document_id = self._get_unit(req.profile_id, req.unit_order)
        chunks = await self._fetch_chunks(document_id, unit)

        llm = get_llm_client()
        question = await generate_question(
            llm, title=unit.title, focus=unit.focus, chunks=chunks
        )

        session = self.repo.create_session(
            profile_id=req.profile_id,
            curriculum_unit_order=req.unit_order,
            concept_id=unit.concept_id,
            session_type="pdf_concept",
        )
        self.repo.add_step(session.id, "question", question)

        return StartSessionResponse(session_id=session.id, question=question)

    async def start_prerequisite_session(
        self, parent_session_id: uuid.UUID
    ) -> StartPrerequisiteResponse:
        """answer_reveal 이후 호출: 선수 개념 세션을 새로 만들어 반환."""
        parent = self.repo.get_session(parent_session_id)
        if parent is None:
            raise HTTPException(status_code=404, detail="학습 세션을 찾을 수 없습니다.")

        hint_1 = self.repo.get_step_by_type(parent_session_id, "hint_1")
        analysis = hint_1.missing_concept_analysis if hint_1 else None
        missing_concept = (
            str(analysis.get("missing_concept", "")) if analysis else ""
        ) or getattr(parent, "prereq_concept_title", None) or parent.concept_id

        parent_title = (
            getattr(parent, "prereq_concept_title", None) or parent.concept_id
        )

        llm = get_llm_client()
        prereq_info = await infer_prerequisite_concept(
            llm,
            parent_concept=parent_title,
            missing_concept=missing_concept,
        )
        prereq_title: str = prereq_info["title"]
        why: str = prereq_info["why"]
        is_foundational: bool = prereq_info["is_foundational"]
        new_depth: int = getattr(parent, "depth", 0) + 1
        prereq_concept_id = f"prereq_{new_depth}_{prereq_title[:40].replace(' ', '_')}"

        question = await generate_prereq_question(llm, title=prereq_title, why=why)

        session = self.repo.create_session(
            profile_id=parent.profile_id,
            curriculum_unit_order=-1,
            concept_id=prereq_concept_id,
            session_type="prerequisite",
            parent_session_id=parent.id,
            depth=new_depth,
            prereq_concept_title=prereq_title,
        )
        self.repo.add_step(session.id, "question", question)

        return StartPrerequisiteResponse(
            session_id=session.id,
            prereq_concept_title=prereq_title,
            why=why,
            question=question,
            depth=new_depth,
            is_foundational=is_foundational,
        )

    async def respond(
        self, session_id: uuid.UUID, user_response: str
    ) -> RespondCorrectResponse | RespondIncorrectResponse:
        session = self.repo.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="학습 세션을 찾을 수 없습니다.")
        if session.status == "completed":
            raise HTTPException(status_code=409, detail="이미 완료된 세션입니다.")

        question_step = self.repo.get_step_by_type(session_id, "question")
        if question_step is None:
            raise HTTPException(status_code=409, detail="질문 단계가 없습니다.")

        title, _focus, chunks, _content = await self._get_session_context(session)

        llm = get_llm_client()
        verdict = await judge_response(
            llm,
            concept=title,
            question=question_step.content,
            user_response=user_response,
            chunks=chunks,
        )
        is_correct = bool(verdict["correct"])
        self.repo.update_step_response(question_step, user_response, is_correct)

        if is_correct:
            self.repo.update_session_status(session, "completed")
            return RespondCorrectResponse(feedback=str(verdict["feedback"]))

        hint = await generate_hint_1(
            llm,
            title=title,
            question=question_step.content,
            user_response=user_response,
        )
        analysis = await infer_missing_concept(
            llm,
            question=question_step.content,
            user_response=user_response,
            concept=title,
            chunks=chunks,
        )
        self.repo.add_step(
            session_id,
            "hint_1",
            hint,
            missing_concept_analysis=analysis,
        )
        return RespondIncorrectResponse(
            hint=hint,
            missing_concept=str(analysis["missing_concept"]),
            reason=str(analysis["reason"]),
        )

    async def get_hint(self, session_id: uuid.UUID) -> HintResponse:
        session = self.repo.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="학습 세션을 찾을 수 없습니다.")

        question_step = self.repo.get_step_by_type(session_id, "question")
        if question_step is None:
            raise HTTPException(status_code=409, detail="질문 단계가 없습니다.")

        hint_1 = self.repo.get_step_by_type(session_id, "hint_1")
        if hint_1 is None:
            raise HTTPException(status_code=409, detail="먼저 답변을 제출해 주세요.")

        hint_2 = self.repo.get_step_by_type(session_id, "hint_2")
        answer_reveal = self.repo.get_step_by_type(session_id, "answer_reveal")

        title, _focus, chunks, unit_content = await self._get_session_context(session)
        llm = get_llm_client()
        is_prereq = getattr(session, "session_type", "pdf_concept") == "prerequisite"

        if hint_2 is None:
            content = await generate_hint_2(
                llm,
                title=title,
                question=question_step.content,
                user_response=question_step.user_response or "",
                chunks=chunks,
            )
            self.repo.add_step(session_id, "hint_2", content)
            return HintResponse(step_type="hint_2", content=content)

        if answer_reveal is None:
            if is_prereq:
                content = await generate_prereq_answer_reveal(
                    llm,
                    title=title,
                    question=question_step.content,
                )
            else:
                content = await generate_answer_reveal(
                    llm,
                    title=title,
                    question=question_step.content,
                    chunks=chunks,
                    unit_content=unit_content,
                )
            self.repo.add_step(session_id, "answer_reveal", content)
            self.repo.update_session_status(session, "completed")
            return HintResponse(step_type="answer_reveal", content=content)

        return HintResponse(step_type="answer_reveal", content=answer_reveal.content)

    def complete_session(self, session_id: uuid.UUID) -> CompleteSessionResponse:
        """세션 완료 후 약점 목록 갱신. prerequisite 세션은 부모로 복귀."""
        session = self.repo.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="학습 세션을 찾을 수 없습니다.")

        if getattr(session, "session_type", "pdf_concept") == "prerequisite":
            if session.status != "completed":
                self.repo.update_session_status(session, "completed")
            return CompleteSessionResponse(
                concept_id=session.concept_id,
                resolved=True,
                current_weaknesses=[],
                return_to_session_id=getattr(session, "parent_session_id", None),
            )

        return update_weakness_after_session(session_id, self.db)
