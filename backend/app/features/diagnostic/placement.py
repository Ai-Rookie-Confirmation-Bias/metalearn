"""[3.Service] 배치고사 — 짧은 진단으로 바닥(floor)만 찾는다 (ISSUE-015, UUID 포팅).

팀원의 임시 진단 스코핑(_select_diag_targets)을 대체하는 정식 구현. 목적은
"수준 확정"이 아니라 학습 시작 좌표 하나 — 정밀 판정은 학습 중(팀 학습 루프의
BKT)으로 이관됐다.

두 모드 (문서 프로파일 분기 — 정제 스캔 산출물 첫 실전 소비):
- linked(사슬형, 수학): 천장(마지막 파트 대표)에서 선수 사슬을 타고 하강.
  첫 오답 1홉, 이후 2홉 건너뛰기. 맞추면 그 지점이 바닥. 이른 정답(2문항
  미만)은 확인 1문항으로 찍기 방어. 선수 에지가 없으면 이전 파트 대표로 폴백.
- enumerative(나열형, 자격증): 파트별 대표 1문항 — 파트 간 선수관계가 없어
  하강이 무의미. 바닥 = 첫 오답 파트의 대표.

노이즈 파트 제외(ISSUE-018): special 파트(특집/부록) + 꼬마 파트를 대표
후보에서 뺀다. 공통 상한 12. 종료 시 SeedService.finalize_placement로 enrollment
확정. 모든 응답은 세션 ConceptMastery(BKT)에 기록 → mastery 시드가 재사용.

⚠️ ISSUE-019 데드락 회피: enrollment/세션 락을 잡은 채 LLM을 await하지 않는다.
문항 생성(LLM) 직전에 반드시 commit해 락을 놓는다. (팀원 record_attempt와 동일 원칙)
"""
import logging
import statistics
import uuid

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.features.diagnostic import bkt
from app.features.diagnostic.models import DiagnosticQuestion, DiagnosticSession
from app.features.diagnostic.schemas import PlacementState, QuestionOut
from app.features.diagnostic.service import DiagnosticService
from app.features.learning.models import ConceptMastery
from app.features.materials.models import DocChunk, Document
from app.features.seed.models import Concept, ConceptEdge, Course

_log = logging.getLogger("uvicorn.error")

_MAX_QUESTIONS = 12
_SKIP_HOP = 2  # 두 번째 오답부터 선수 사슬을 건너뛰는 보폭


class PlacementService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.diag = DiagnosticService(db)  # 문항 생성·검증·채점 인프라 재사용

    # ── 시작 ─────────────────────────────────────────────────
    async def start(self, course_id: uuid.UUID) -> PlacementState:
        course = self.db.get(Course, course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="코스를 찾을 수 없습니다.")
        document = self.db.get(Document, course.document_id)
        profile = (document.profile if document else None) or "enumerative"
        mode = "linked" if profile == "linked" else "enumerative"

        reps = self._part_representatives(course_id, course.document_id)
        if not reps:
            raise HTTPException(
                status_code=400,
                detail="대표 개념이 없는 코스입니다. seed tree를 먼저 실행하세요.",
            )

        plan = [str(c.id) for c in reps][:_MAX_QUESTIONS]
        current = plan[0] if mode == "enumerative" else plan[-1]

        session = DiagnosticSession(
            course_id=course_id,
            kind="placement",
            state={
                "mode": mode,
                "plan": plan,
                "asked": [],  # [{concept_id, correct}]
                "current": current,
                "anchor": len(plan) - 1,
                "confirming": False,
                "wrong_streak": 0,
                "ceiling": plan[-1],
                "user_id": str(course.user_id),
            },
        )
        self.db.add(session)
        self.diag.repo.set_enrollment_diag_status(
            user_id=course.user_id, course_id=course_id, status="in_progress"
        )
        self.db.commit()  # ⚠️ LLM 호출 전 락 해제 (ISSUE-019)

        question = await self._serve_question(session, uuid.UUID(current))
        self.db.commit()
        return self._state(session, question)

    # ── 응답 ─────────────────────────────────────────────────
    async def answer(
        self,
        session_id: uuid.UUID,
        question_id: uuid.UUID,
        selected_index: int | None = None,
        answer_text: str | None = None,
    ) -> PlacementState:
        session = self.db.get(DiagnosticSession, session_id)
        if session is None or session.kind != "placement":
            raise HTTPException(status_code=404, detail="배치고사 세션을 찾을 수 없습니다.")
        if session.status == "completed":
            raise HTTPException(status_code=409, detail="이미 종료된 배치고사입니다.")
        question = self.db.get(DiagnosticQuestion, question_id)
        if question is None or question.session_id != session_id or question.answered:
            raise HTTPException(status_code=404, detail="답할 수 있는 문항이 아닙니다.")

        correct = await self.diag._grade(question, selected_index, answer_text)
        question.answered = True
        question.is_active = False
        question.selected_index = selected_index
        question.answer_text = answer_text
        question.is_correct = correct

        state = dict(session.state or {})
        self._record(session, state, question.concept_id, correct)

        next_concept_id = self._next(state, correct)
        if next_concept_id is None or len(state["asked"]) >= _MAX_QUESTIONS:
            session.state = state
            result = await self._complete(session, state)
            self.db.commit()
            return result

        state["current"] = str(next_concept_id)
        session.state = state
        self.db.commit()  # ⚠️ LLM 호출 전 락 해제 (ISSUE-019)

        next_q = await self._serve_question(session, next_concept_id)
        self.db.commit()
        return self._state(session, next_q)

    # ── 하강 알고리즘 ─────────────────────────────────────────
    def _next(self, state: dict, correct: bool) -> uuid.UUID | None:
        mode = state["mode"]
        asked_ids = {a["concept_id"] for a in state["asked"]}

        if mode == "enumerative":
            for cid in state["plan"]:
                if cid not in asked_ids:
                    return uuid.UUID(cid)
            return None

        # linked — depth 하강
        current = uuid.UUID(state["current"])
        if correct:
            if state["confirming"] or len(state["asked"]) >= 3:
                state["floor"] = str(current)
                return None
            state["confirming"] = True  # 이른 정답 → 확인 1문항
            return current

        state["confirming"] = False
        state["wrong_streak"] = state.get("wrong_streak", 0) + 1
        hop = 1 if state["wrong_streak"] <= 1 else _SKIP_HOP
        node = current
        for _ in range(hop):
            nxt = self._first_prerequisite(node, exclude=asked_ids)
            if nxt is None:
                anchor = state.get("anchor", 0)
                if anchor > 0:
                    anchor -= 1
                    state["anchor"] = anchor
                    cand = state["plan"][anchor]
                    if cand not in asked_ids:
                        nxt = uuid.UUID(cand)
                    else:
                        continue
            if nxt is None:
                break
            node = nxt
        if node == current or str(node) in asked_ids:
            state["floor"] = str(current)
            return None
        return node

    def _first_prerequisite(
        self, concept_id: uuid.UUID, exclude: set[str]
    ) -> uuid.UUID | None:
        rows = list(
            self.db.scalars(
                select(Concept)
                .join(ConceptEdge, ConceptEdge.to_concept_id == Concept.id)
                .where(
                    ConceptEdge.from_concept_id == concept_id,
                    ConceptEdge.kind == "prerequisite",
                )
                .order_by(Concept.created_at, Concept.id)
            )
        )
        for preferred in ("book", "ai_prereq"):
            for c in rows:
                if c.source == preferred and str(c.id) not in exclude:
                    return c.id
        return None

    # ── 종료 ─────────────────────────────────────────────────
    async def _complete(self, session: DiagnosticSession, state: dict) -> PlacementState:
        from app.features.seed.service import SeedService

        asked = state["asked"]
        if state["mode"] == "enumerative":
            floor = next((a["concept_id"] for a in asked if not a["correct"]), None)
        else:
            floor = state.get("floor") or (asked[-1]["concept_id"] if asked else None)
        floor_uuid = uuid.UUID(floor) if floor else None
        ceiling_uuid = uuid.UUID(state["ceiling"]) if state.get("ceiling") else None

        self.diag.repo.complete_session(session)
        seed = await SeedService(self.db).finalize_placement(
            session.course_id,
            floor_id=floor_uuid,
            ceiling_id=ceiling_uuid,
            diag_q_count=len(asked),
        )
        _log.info(
            "배치고사 종료: course %s, %d문항, floor=%s (%s 모드)",
            session.course_id, len(asked), floor, state["mode"],
        )
        return PlacementState(
            session_id=session.id,
            done=True,
            asked=len(asked),
            max_questions=_MAX_QUESTIONS,
            question=None,
            floor_concept=floor_uuid,
            ceiling_concept=ceiling_uuid,
            weak_concept_ids=[uuid.UUID(a["concept_id"]) for a in asked if not a["correct"]],
            seed=_jsonable(seed),
        )

    # ── 문항·기록 헬퍼 ────────────────────────────────────────
    async def _serve_question(
        self, session: DiagnosticSession, concept_id: uuid.UUID
    ) -> DiagnosticQuestion:
        concept = self.db.get(Concept, concept_id)
        if concept is None:
            raise HTTPException(status_code=500, detail="개념이 사라졌습니다.")
        try:
            draft = await self.diag._generate_draft(concept)
        except (ValidationError, ValueError):
            draft = await self.diag._generate_draft(concept)  # 플레이크 1회 재시도
        # 검증 패스 재사용(ISSUE-016): 오답 문항이면 1회 재생성
        invalid = await self.diag._verify_drafts([(concept, draft)])
        if invalid:
            try:
                draft = await self.diag._generate_draft(concept)
            except (ValidationError, ValueError):
                _log.warning("배치고사 재생성 실패 — 원본 사용: %s", concept.name)
        question = self.diag._persist_draft(session.id, concept.id, draft)
        question.is_active = True
        self.db.flush()
        return question

    def _record(
        self, session: DiagnosticSession, state: dict, concept_id: uuid.UUID, correct: bool
    ) -> None:
        state["asked"] = [
            *state["asked"], {"concept_id": str(concept_id), "correct": correct}
        ]
        user_id = uuid.UUID(state["user_id"])
        mastery = self.db.get(ConceptMastery, (user_id, concept_id))
        if mastery is None:
            mastery = ConceptMastery(
                user_id=user_id,
                concept_id=concept_id,
                session_id=session.id,
                strength=settings.BKT_P_INIT,
                answered_count=0,
            )
            self.db.add(mastery)
        else:
            mastery.session_id = session.id
        mastery.strength = bkt.update(
            mastery.strength, correct=correct, params=self.diag._params("mcq")
        )
        mastery.answered_count = (mastery.answered_count or 0) + 1
        mastery.resolved = True  # 배치고사 응답은 시드 신호로 확정 취급
        self.db.flush()

    def _part_representatives(
        self, course_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[Concept]:
        """파트당 대표 1개 — 문서순. 노이즈 파트 필터(ISSUE-018): special(내용)
        + 꼬마 파트(크기) 제외, 전멸 시 무필터 폴백. 배제는 배치고사 한정 —
        커리큘럼 트리엔 유지된다."""
        chunk_part: dict[uuid.UUID, int] = {}
        chunk_order: dict[uuid.UUID, int] = {}
        for row in self.db.scalars(
            select(DocChunk).where(DocChunk.document_id == document_id)
        ):
            chunk_part[row.id] = row.part_index or 0
            chunk_order[row.id] = row.chunk_index

        document = self.db.get(Document, document_id)
        scan_parts = ((document.refined_elements or {}).get("scan") or {}).get("parts") or []
        special_parts = {i + 1 for i, p in enumerate(scan_parts) if p.get("kind") == "special"}

        book_concepts = list(
            self.db.scalars(
                select(Concept).where(
                    Concept.course_id == course_id, Concept.source == "book"
                )
            )
        )

        def part_of(c: Concept) -> int:
            return chunk_part.get(c.source_chunk_id, 0) if c.source_chunk_id else 0

        def order_of(c: Concept) -> int:
            return chunk_order.get(c.source_chunk_id, -1) if c.source_chunk_id else -1

        part_counts: dict[int, int] = {}
        for c in book_concepts:
            part_counts[part_of(c)] = part_counts.get(part_of(c), 0) + 1

        reps_sorted = sorted(
            (c for c in book_concepts if c.depth_level == 0),
            key=lambda c: (part_of(c), order_of(c), str(c.id)),
        )
        distinct_parts = {part_of(c) for c in reps_sorted}
        if len(distinct_parts) <= 1:
            # 스캔이 파트를 못 잡은 단일 파트 문서: 섹션 대표(depth-0)를 문서순
            # 샘플 단위로 삼는다 — 파트 기준으로 뽑으면 1개로 붕괴하므로.
            picked = reps_sorted
        else:
            picked = []
            seen_parts: set[int] = set()
            for c in reps_sorted:
                if part_of(c) not in seen_parts:
                    seen_parts.add(part_of(c))
                    picked.append(c)

        if special_parts:
            filtered = [c for c in picked if part_of(c) not in special_parts]
            if filtered and len(filtered) < len(picked):
                _log.info("배치고사 special 파트 제외: %d개", len(picked) - len(filtered))
                picked = filtered

        if len(part_counts) >= 3:
            threshold = statistics.median(part_counts.values()) * 0.2
            filtered = [c for c in picked if part_counts[part_of(c)] >= threshold]
            if filtered and len(filtered) < len(picked):
                _log.info("배치고사 꼬마 파트 제외: %d개 (임계 %.1f)",
                          len(picked) - len(filtered), threshold)
            if filtered:
                picked = filtered
        return picked

    def _state(
        self, session: DiagnosticSession, question: DiagnosticQuestion
    ) -> PlacementState:
        concept = self.db.get(Concept, question.concept_id)
        state = session.state or {}
        return PlacementState(
            session_id=session.id,
            done=False,
            asked=len(state.get("asked", [])),
            max_questions=_MAX_QUESTIONS,
            question=QuestionOut(
                id=question.id,
                concept_id=question.concept_id,
                concept_name=concept.name if concept else "",
                qtype=question.qtype,  # type: ignore[arg-type]
                question=question.question,
                options=list(question.options) if question.options else [],
            ),
        )


def _jsonable(obj: object) -> object:
    """finalize_placement 반환의 UUID를 응답 직렬화 가능하게 문자열화."""
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    return obj
