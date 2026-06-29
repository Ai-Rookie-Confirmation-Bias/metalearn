"""[3.Service] 설문 → 진단 → 약점 → Seed 슬라이스."""
from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.document_intelligence.factory import get_document_intelligence
from app.core.llm.factory import get_llm_client
from app.features.materials.repository import MaterialsRepository
from app.features.materials.schemas import DocumentSkeleton
from app.features.seed.concept_sources import build_concept_sources
from app.features.seed.content_generator import generate_all_unit_contents
from app.features.seed.curriculum import (
    build_chapter_groups,
    build_curriculum_units,
    enrich_curriculum_units_local,
)
from app.features.seed.diagnostic import build_diagnostic_questions
from app.features.seed.repository import SeedRepository
from app.features.seed.weakness_utils import weakness_concept_ids
from app.features.seed.schemas import (
    CurriculumResponse,
    CurriculumUnit,
    CurriculumChapterGroup,
    DiagnosticQuestionPublic,
    DiagnosticResultResponse,
    DiagnosticSessionResponse,
    LearningRange,
    PrerequisiteAnalysis,
    PrerequisiteAnalyzeRequest,
    SeedProfileResponse,
    SeedSlice,
    SubmitDiagnosticRequest,
    SurveyRequest,
)


class SeedService:
    def __init__(self, db: Session) -> None:
        self.repo = SeedRepository(db)
        self.materials = MaterialsRepository(db)

    def _load_skeleton(self, document_id: uuid.UUID) -> DocumentSkeleton:
        doc = self.materials.get_document(document_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
        if doc.parse_status != "parsed" or not doc.skeleton:
            raise HTTPException(status_code=409, detail="문서 파싱이 완료되지 않았습니다.")
        clean = {k: v for k, v in doc.skeleton.items() if not str(k).startswith("_")}
        return DocumentSkeleton.model_validate(clean)

    @staticmethod
    def _resolve_concepts_in_range(
        skeleton: DocumentSkeleton, learning_range: LearningRange
    ) -> list[str]:
        toc_by_id = {t.id: t for t in skeleton.toc}
        start = toc_by_id.get(learning_range.start)
        end = toc_by_id.get(learning_range.end)

        if start and end:
            lo = min(start.start_page, end.start_page)
            hi = max(start.end_page, end.end_page)
            return [
                c.id
                for c in skeleton.concepts
                if any(lo <= p <= hi for p in c.page_numbers)
            ]

        # chapter_id가 아닌 concept_id 직접 지정 fallback
        concept_ids = [c.id for c in skeleton.concepts]
        if learning_range.start in concept_ids and learning_range.end in concept_ids:
            i0 = concept_ids.index(learning_range.start)
            i1 = concept_ids.index(learning_range.end)
            lo, hi = sorted((i0, i1))
            return concept_ids[lo : hi + 1]

        raise HTTPException(status_code=400, detail="학습 범위(start/end)가 유효하지 않습니다.")

    def submit_survey(self, req: SurveyRequest) -> SeedProfileResponse:
        skeleton = self._load_skeleton(req.document_id)
        concepts = self._resolve_concepts_in_range(skeleton, req.learning_range)

        profile = self.repo.create_profile(
            document_id=req.document_id,
            learning_range=req.learning_range.model_dump(),
            learning_goal=req.learning_goal,
            concepts_in_range=concepts,
        )
        return SeedProfileResponse.model_validate(profile)

    async def start_diagnostic(self, profile_id: uuid.UUID) -> DiagnosticSessionResponse:
        profile = self.repo.get_profile(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Seed 프로필을 찾을 수 없습니다.")

        skeleton = self._load_skeleton(profile.document_id)
        chunks = self.materials.list_chunks(profile.document_id)
        sources = build_concept_sources(skeleton, chunks, profile.concepts_in_range)

        gen = await build_diagnostic_questions(
            profile.concepts_in_range,
            sources,
        )

        if not gen.questions:
            raise HTTPException(status_code=409, detail="진단 문제를 생성할 개념이 없습니다.")

        session = self.repo.create_session(profile_id)
        questions: list[DiagnosticQuestionPublic] = []
        for spec in gen.questions:
            q = self.repo.add_question(
                session_id=session.id,
                concept_id=spec["concept_id"],
                question_text=spec["question_text"],
                options=spec["options"],
                correct_index=spec["correct_index"],
                source_chunk_id=spec.get("source_chunk_id"),
            )
            questions.append(
                DiagnosticQuestionPublic(
                    id=q.id,
                    concept_id=q.concept_id,
                    question_text=q.question_text,
                    options=q.options,
                )
            )

        return DiagnosticSessionResponse(
            id=session.id,
            profile_id=profile_id,
            status=session.status,
            questions=questions,
            generation_mode=gen.generation_mode,  # type: ignore[arg-type]
            generation_note=gen.generation_note,
        )

    def submit_diagnostic(
        self, session_id: uuid.UUID, req: SubmitDiagnosticRequest
    ) -> DiagnosticResultResponse:
        session = self.repo.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="진단 세션을 찾을 수 없습니다.")
        if session.status == "completed":
            raise HTTPException(status_code=409, detail="이미 제출된 진단 세션입니다.")

        questions = {q.id: q for q in self.repo.list_questions(session_id)}
        if not questions:
            raise HTTPException(status_code=409, detail="진단 문항이 없습니다.")

        weaknesses: list[str] = []
        correct_count = 0

        for item in req.answers:
            q = questions.get(item.question_id)
            if q is None:
                raise HTTPException(status_code=400, detail=f"문항 {item.question_id} 없음")
            is_correct = item.choice_index == q.correct_index
            if is_correct:
                correct_count += 1
            else:
                weaknesses.append(q.concept_id)
            self.repo.add_answer(q.id, item.choice_index, is_correct)

        self.repo.finish_session(session)
        profile = self.repo.get_profile(session.profile_id)
        assert profile is not None

        # 중복 concept_id 제거, 순서 유지
        seen: set[str] = set()
        unique_weaknesses = [w for w in weaknesses if not (w in seen or seen.add(w))]

        self.repo.update_profile(
            profile, weaknesses=unique_weaknesses, status="diagnostic_done"
        )

        score = correct_count / len(questions) if questions else 0.0
        return DiagnosticResultResponse(
            session_id=session_id,
            profile_id=profile.id,
            weaknesses=unique_weaknesses,
            score=score,
            status="completed",
        )

    def get_slice(self, profile_id: uuid.UUID) -> SeedSlice:
        profile = self.repo.get_profile(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Seed 프로필을 찾을 수 없습니다.")
        if profile.status != "diagnostic_done":
            raise HTTPException(status_code=409, detail="진단 완료 후 Seed 슬라이스를 조회할 수 있습니다.")

        return SeedSlice(
            document_id=profile.document_id,
            profile_id=profile.id,
            learning_range=LearningRange.model_validate(profile.learning_range),
            learning_goal=profile.learning_goal,
            concepts_in_range=profile.concepts_in_range,
            weaknesses=profile.weaknesses,
        )

    def get_profile(self, profile_id: uuid.UUID) -> SeedProfileResponse:
        profile = self.repo.get_profile(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Seed 프로필을 찾을 수 없습니다.")
        return SeedProfileResponse.model_validate(profile)

    def _to_curriculum_response(
        self,
        profile,
        curriculum,
        *,
        generation_mode: str = "local",
        generation_note: str | None = None,
    ) -> CurriculumResponse:
        units = [CurriculumUnit.model_validate(u) for u in curriculum.units]
        groups = [
            CurriculumChapterGroup(
                chapter_id=g.get("chapter_id"),
                chapter_title=g["chapter_title"],
                units=[CurriculumUnit.model_validate(u) for u in g["units"]],
            )
            for g in curriculum.chapter_groups
        ]
        return CurriculumResponse(
            id=curriculum.id,
            profile_id=curriculum.profile_id,
            document_id=profile.document_id,
            learning_goal=profile.learning_goal,
            weakness_count=curriculum.weakness_count,
            total_units=curriculum.total_units,
            units=units,
            chapter_groups=groups,
            generation_mode=generation_mode,  # type: ignore[arg-type]
            generation_note=generation_note,
            created_at=curriculum.created_at,
        )

    async def analyze_prerequisites(self, req: PrerequisiteAnalyzeRequest) -> PrerequisiteAnalysis:
        skeleton = self._load_skeleton(req.document_id)
        intelligence = get_document_intelligence()
        return await intelligence.analyze_prerequisites(skeleton, req.learning_range)

    async def generate_curriculum(self, profile_id: uuid.UUID) -> CurriculumResponse:
        profile = self.repo.get_profile(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Seed 프로필을 찾을 수 없습니다.")
        if profile.status != "diagnostic_done":
            raise HTTPException(
                status_code=409,
                detail="진단 완료 후 커리큘럼을 생성할 수 있습니다.",
            )

        skeleton = self._load_skeleton(profile.document_id)
        chunks = self.materials.list_chunks(profile.document_id)
        sources = build_concept_sources(skeleton, chunks, profile.concepts_in_range)

        units = build_curriculum_units(
            profile.concepts_in_range,
            profile.weaknesses,
            skeleton,
        )
        if not units:
            raise HTTPException(status_code=409, detail="커리큘럼을 구성할 개념이 없습니다.")

        weakness_count = sum(1 for u in units if u["priority"] == "weakness")

        gen_mode = "local"
        gen_note: str | None = None
        if settings.use_mock_ai:
            units = enrich_curriculum_units_local(
                units, profile.weaknesses, profile.learning_goal
            )
            gen_note = "API 키 없음 — 규칙 기반 로드맵"
        else:
            llm = get_llm_client()

            # 1단계: summary/focus enrich
            intelligence = get_document_intelligence()
            enriched = await intelligence.enrich_curriculum_units(
                units,
                skeleton,
                profile.learning_goal,
                weakness_concept_ids(profile.weaknesses),
            )
            if enriched != units and any(u.get("summary") for u in enriched):
                units = enriched
                gen_mode = "llm"
            else:
                units = enrich_curriculum_units_local(
                    units, profile.weaknesses, profile.learning_goal
                )

            # 2단계: 단원별 학습 콘텐츠 생성 (Solar가 PDF 원문으로 설명 작성)
            units = await generate_all_unit_contents(
                units=units,
                sources=sources,
                learning_goal=profile.learning_goal,
                weaknesses=profile.weaknesses,
                llm=llm,
            )
            has_content = any(u.get("content") for u in units)
            if has_content:
                gen_mode = "llm"
                gen_note = f"{settings.llm_provider_label}로 학습 콘텐츠 생성"
            else:
                gen_note = f"{settings.llm_provider_label} 콘텐츠 생성 실패 — 규칙 기반 로드맵"

        chapter_groups = build_chapter_groups(units, skeleton.toc)

        curriculum = self.repo.create_curriculum(
            profile_id=profile_id,
            units=units,
            chapter_groups=chapter_groups,
            weakness_count=weakness_count,
            total_units=len(units),
        )
        self.repo.update_profile(profile, status="curriculum_ready")

        refreshed = self.repo.get_profile(profile_id)
        assert refreshed is not None
        return self._to_curriculum_response(
            refreshed,
            curriculum,
            generation_mode=gen_mode,
            generation_note=gen_note,
        )

    def get_curriculum(self, profile_id: uuid.UUID) -> CurriculumResponse:
        profile = self.repo.get_profile(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Seed 프로필을 찾을 수 없습니다.")

        curriculum = self.repo.get_curriculum_by_profile(profile_id)
        if curriculum is None:
            raise HTTPException(
                status_code=404,
                detail="커리큘럼이 없습니다. 먼저 생성해 주세요.",
            )
        return self._to_curriculum_response(profile, curriculum)
