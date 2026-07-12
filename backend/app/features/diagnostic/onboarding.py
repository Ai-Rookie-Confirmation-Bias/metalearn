"""[3.Service] 온보딩 진단 — 성향 프로파일링 + 기반지식 체크 (진단 재설계).

배치고사(placement, floor 찾기)를 대체하는 실사용 경로. 목적이 다르다:
수준 좌표를 찾아 범위를 자르는 게 아니라, ① 이 사람이 "어떻게" 배우는지
(성향 3축)를 재고 ② 교재가 전제하는 밑바탕 중 비어 있는 게 있는지(갭 목록)를
확인한다. 커리큘럼은 이후 전 절 todo로 깔린다 — 아무것도 잠그거나 건너뛰지 않는다.

3단계 상태기계 (세션 state JSONB):
  disposition  고정 상황판단 4문항 — LLM 불필요, 즉답, 정답 없음
  probe        같은 개념을 두 스타일(비유 vs 원리)로 설명 → 선호 선택
               (자기보고가 아닌 관찰 신호 + 교재 첫 만남 겸용)
  quiz         기반지식 체크 — 첫 파트 입구에서 선수 사슬을 최대 2단 하강
               (기존 배치고사의 하강 엔진 재활용, 산출물은 floor가 아니라 갭)

종료 시 서버가 한 번에 확정: 성향 프로파일 upsert + 전 절 todo 시딩 +
갭 기록(enrollment.self_report) + (상한 2) 선수 에지 역주입.
프론트는 결과(프로필 카드)를 보여주고 이동만 한다.

⚠️ ISSUE-019: 락을 잡은 채 LLM을 await하지 않는다 — LLM 호출 전 commit.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.features.diagnostic import bkt
from app.features.diagnostic.models import DiagnosticQuestion, DiagnosticSession
from app.features.diagnostic.placement import PlacementService
from app.features.diagnostic.schemas import (
    DispositionItemOut,
    FoundationGapOut,
    OnboardingResult,
    OnboardingState,
    ProbeOut,
    QuestionOut,
)
from app.features.diagnostic.service import DiagnosticService
from app.features.learning.models import ConceptMastery
from app.features.seed.models import Concept, ConceptEdge, Course

_log = logging.getLogger("uvicorn.error")

# 문항 예산 — "시험"이 아니라 "나를 알아가는 3~4분"이 목표.
_ENTRY_COUNT = 3          # 기반 체크 진입 개념 수(첫 파트 대표들)
_MAX_DEPTH = 2            # 선수 사슬 하강 상한
_MAX_CONTENT_QUESTIONS = 6  # 내용 문항 총 상한(프로브 인출 포함)
_INJECT_CAP = 2           # 선수 에지 역주입 상한(그래프 오염 방지)

# 정답 시 선수 1홉에 얹는 가벼운 상향 시드 — "이걸 안다면 직접 선수도 알
# 가능성이 높다". 학습 루프의 선행 결손 오탐(행 없음=0.0)을 줄인다.
_KNOWN_PREREQ_STRENGTH = 0.6

# ── 성향 고정 문항 (LLM 불필요 — 재현성·비용 0·즉답) ─────────────────
# 자기평가("비유파인가요?")가 아니라 구체 상황 강제선택으로 잰다.
# options: (표시 문구, 축 신호 0..1)
_DISPOSITION_ITEMS: list[dict] = [
    {
        "id": "rep1",
        "axis": "representation",
        "prompt": "낯선 개념을 처음 만났을 때, 어떤 설명이 더 빨리 와닿나요?",
        "options": [
            ("실생활 비유나 구체적인 예시부터 보여주는 설명", 1.0),
            ("정확한 정의와 원리부터 짚어주는 설명", 0.0),
        ],
    },
    {
        "id": "rig1",
        "axis": "rigor",
        "prompt": "공식을 배워서 문제는 풀리는데, 왜 그렇게 되는지는 모르겠어요. 이때 나는…",
        "options": [
            ("일단 진도를 나간다. 쓰다 보면 이해된다", 0.0),
            ("찜찜해서 원리를 파악한 뒤에야 넘어간다", 1.0),
        ],
    },
    {
        "id": "ctx1",
        "axis": "context",
        "prompt": "새 단원을 시작할 때 먼저 알고 싶은 것은?",
        "options": [
            ("이게 왜 필요하고 어디서 나왔는지 — 배경 이야기", 1.0),
            ("핵심 내용과 사용법 — 본론부터", 0.0),
        ],
    },
    {
        "id": "rig2",
        "axis": "rigor",
        "prompt": "시험 전날, 나의 마무리 공부법에 가까운 것은?",
        "options": [
            ("요약본과 암기 카드로 핵심을 정리한다", 0.0),
            ("원리를 다시 훑으며 스스로 설명해 본다", 1.0),
        ],
    },
]

_PROBE_SYSTEM = (
    "너는 학습 콘텐츠 작가다. 같은 개념을 두 가지 방식으로 짧게 설명한다. "
    "출력은 지정한 JSON 스키마만 따른다."
)


def _probe_prompt(concept: Concept, excerpt: str | None) -> str:
    grounding = (
        f"\n\n=== 교재 원문 발췌 ===\n{excerpt[:1500]}\n=== 발췌 끝 ===\n"
        "규칙: 두 설명 모두 위 원문 내용에 근거할 것. 원문에 없는 사실 금지.\n"
        if excerpt
        else ""
    )
    return (
        f"개념 '{concept.name}'을 처음 배우는 학습자에게 두 가지 방식으로 "
        f"각각 3~4문장씩 한국어로 설명하라.\n"
        f"개념 설명: {concept.description or '(없음)'}\n"
        f"{grounding}\n"
        "variant_a(비유·예시 중심): 실생활 비유나 구체 예시로 감을 먼저 잡게 하라. "
        "정의는 마지막에 한 문장으로.\n"
        "variant_b(정의·원리 중심): 정확한 정의에서 출발해 원리를 짧게 전개하라. "
        "비유 없이.\n\n"
        '출력 JSON: {"variant_a": str, "variant_b": str}'
    )


class OnboardingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.diag = DiagnosticService(db)  # 문항 생성·검증·채점 인프라 재사용
        self.placement = PlacementService(db)  # 대표 선정·선수 사슬 재활용

    # ── 시작 ─────────────────────────────────────────────────
    async def start(
        self, course_id: uuid.UUID, purpose: str | None = None
    ) -> OnboardingState:
        course = self.db.get(Course, course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="코스를 찾을 수 없습니다.")
        # 위저드 STEP 3의 학습 목적 — 세션에 실어 종료 시 enrollment로 확정.
        if purpose not in ("exam", "career", "culture", "hobby"):
            purpose = None

        # 기반 체크 진입점 = 교재 '첫 파트' 대표들 — 입구에서 밑바탕을 파본다.
        # (배치고사는 마지막 파트=천장에서 시작했다. 방향이 뒤집힌 지점.)
        reps = self.placement._part_representatives(course_id)
        if not reps:
            raise HTTPException(
                status_code=400,
                detail="대표 개념이 없는 코스입니다. seed tree를 먼저 실행하세요.",
            )
        plan = [str(c.id) for c in reps[:_ENTRY_COUNT]]

        session = DiagnosticSession(
            course_id=course_id,
            kind="onboarding",
            state={
                "user_id": str(course.user_id),
                "purpose": purpose,
                "phase": "disposition",
                "disp_idx": 0,
                "disp_answers": [],
                "probe": None,
                "plan": plan,
                "entry_idx": 0,
                "depth": 0,
                "descents": 0,
                "asked": [],
                "gaps": [],
            },
        )
        self.db.add(session)
        self.diag.repo.set_enrollment_diag_status(
            user_id=course.user_id, course_id=course_id, status="in_progress"
        )
        self.db.commit()
        return self._state(session)

    # ── 응답 ─────────────────────────────────────────────────
    async def answer(
        self,
        session_id: uuid.UUID,
        *,
        choice_index: int | None = None,
        question_id: uuid.UUID | None = None,
        selected_index: int | None = None,
        answer_text: str | None = None,
    ) -> OnboardingState:
        session = self.db.get(DiagnosticSession, session_id)
        if session is None or session.kind != "onboarding":
            raise HTTPException(status_code=404, detail="온보딩 세션을 찾을 수 없습니다.")
        if session.status == "completed":
            raise HTTPException(status_code=409, detail="이미 종료된 온보딩입니다.")

        state = dict(session.state or {})
        phase = state.get("phase")

        if phase == "disposition":
            return await self._answer_disposition(session, state, choice_index)
        if phase == "probe":
            return await self._answer_probe(session, state, choice_index)
        if phase == "quiz":
            return await self._answer_quiz(
                session, state, question_id, selected_index, answer_text
            )
        raise HTTPException(status_code=409, detail="답할 수 있는 단계가 아닙니다.")

    # ── 1단계: 성향 문항 ──────────────────────────────────────
    async def _answer_disposition(
        self, session: DiagnosticSession, state: dict, choice_index: int | None
    ) -> OnboardingState:
        idx = int(state.get("disp_idx", 0))
        if idx >= len(_DISPOSITION_ITEMS):
            raise HTTPException(status_code=409, detail="성향 문항이 남아있지 않습니다.")
        item = _DISPOSITION_ITEMS[idx]
        if choice_index is None or not 0 <= choice_index < len(item["options"]):
            raise HTTPException(status_code=400, detail="choice_index가 필요합니다.")

        state["disp_answers"] = [
            *state["disp_answers"],
            {"item": item["id"], "axis": item["axis"],
             "signal": item["options"][choice_index][1]},
        ]
        state["disp_idx"] = idx + 1

        if state["disp_idx"] < len(_DISPOSITION_ITEMS):
            session.state = state
            self.db.commit()
            return self._state(session)

        # 성향 끝 → 프로브 생성 (LLM — 커밋으로 락을 놓고 호출, ISSUE-019)
        state["phase"] = "probe"
        session.state = state
        self.db.commit()
        await self._prepare_probe(session, state)
        session.state = state
        self.db.commit()
        return self._state(session)

    async def _prepare_probe(self, session: DiagnosticSession, state: dict) -> None:
        concept = self.db.get(Concept, uuid.UUID(state["plan"][0]))
        if concept is None:
            raise HTTPException(status_code=500, detail="진입 개념이 사라졌습니다.")
        excerpt = None
        if concept.source_chunk_id is not None:
            excerpt = self.diag.repo.get_chunk_contents(
                {concept.source_chunk_id}
            ).get(concept.source_chunk_id)
        from app.core.llm.solar import solar_client

        try:
            raw = await solar_client.generate_json(
                _probe_prompt(concept, excerpt), system=_PROBE_SYSTEM
            )
            variant_a = str(raw.get("variant_a") or "").strip()
            variant_b = str(raw.get("variant_b") or "").strip()
        except Exception as exc:  # noqa: BLE001 — 프로브는 보조 신호, 실패해도 진행
            _log.warning("스타일 프로브 생성 실패 — 건너뜀: %s", exc)
            variant_a = variant_b = ""
        if not variant_a or not variant_b:
            # 프로브 생성 실패 → 성향은 고정 문항 신호만으로 가고 바로 퀴즈로
            state["probe"] = {"skipped": True}
            state["phase"] = "quiz"
            await self._serve_entry_question(session, state)
            return
        state["probe"] = {
            "concept_id": str(concept.id),
            "variant_a": variant_a,
            "variant_b": variant_b,
            "choice": None,
        }

    async def _answer_probe(
        self, session: DiagnosticSession, state: dict, choice_index: int | None
    ) -> OnboardingState:
        probe = state.get("probe") or {}
        if probe.get("skipped"):
            raise HTTPException(status_code=409, detail="프로브가 없는 세션입니다.")
        if choice_index not in (0, 1):
            raise HTTPException(status_code=400, detail="choice_index(0|1)가 필요합니다.")
        # 관찰 신호: variant_a(비유) 선택 → representation 1.0, variant_b → 0.0
        probe["choice"] = choice_index
        state["probe"] = probe
        state["phase"] = "quiz"
        session.state = state
        self.db.commit()  # LLM 호출 전 락 해제

        await self._serve_entry_question(session, state)
        session.state = state
        self.db.commit()
        return self._state(session)

    # ── 3단계: 기반지식 체크 (하강 엔진 재활용) ───────────────────
    async def _serve_entry_question(
        self, session: DiagnosticSession, state: dict
    ) -> None:
        """현재 진입/하강 지점 개념의 문항을 생성·활성화. state에 current 기록."""
        concept_id = state.get("current") or state["plan"][state["entry_idx"]]
        state["current"] = str(concept_id)
        await self._make_question(session, uuid.UUID(str(concept_id)))

    async def _make_question(
        self, session: DiagnosticSession, concept_id: uuid.UUID
    ) -> DiagnosticQuestion:
        concept = self.db.get(Concept, concept_id)
        if concept is None:
            raise HTTPException(status_code=500, detail="개념이 사라졌습니다.")
        try:
            draft = await self.diag._generate_draft(concept)
        except (ValidationError, ValueError):
            draft = await self.diag._generate_draft(concept)  # 플레이크 1회 재시도
        invalid = await self.diag._verify_drafts([(concept, draft)])
        if invalid:
            try:
                draft = await self.diag._generate_draft(concept)
            except (ValidationError, ValueError):
                _log.warning("온보딩 문항 재생성 실패 — 원본 사용: %s", concept.name)
        question = self.diag._persist_draft(session.id, concept.id, draft)
        question.is_active = True
        self.db.flush()
        return question

    async def _answer_quiz(
        self,
        session: DiagnosticSession,
        state: dict,
        question_id: uuid.UUID | None,
        selected_index: int | None,
        answer_text: str | None,
    ) -> OnboardingState:
        if question_id is None:
            raise HTTPException(status_code=400, detail="question_id가 필요합니다.")
        question = self.db.get(DiagnosticQuestion, question_id)
        if (
            question is None
            or question.session_id != session.id
            or question.answered
        ):
            raise HTTPException(status_code=404, detail="답할 수 있는 문항이 아닙니다.")

        correct = await self.diag._grade(question, selected_index, answer_text)
        question.answered = True
        question.is_active = False
        question.selected_index = selected_index
        question.answer_text = answer_text
        question.is_correct = correct

        self._record_mastery(state, question, correct)
        root = state["plan"][state["entry_idx"]]
        state["asked"] = [
            *state["asked"],
            {
                "concept_id": str(question.concept_id),
                "correct": correct,
                "root": root,
                "depth": int(state.get("depth", 0)),
            },
        ]

        # 가벼운 정답 공개(사용자 요청) — 답한 문항의 정답만 잠깐 보여주고 진행.
        reveal = self._quiz_reveal(question, correct)

        next_concept = self._next_step(state, question.concept_id, correct)
        if next_concept is None or len(state["asked"]) >= _MAX_CONTENT_QUESTIONS:
            session.state = state
            result = await self._complete(session, state)
            result.last_reveal = reveal
            self.db.commit()
            return result

        state["current"] = str(next_concept)
        session.state = state
        self.db.commit()  # LLM 호출 전 락 해제

        await self._make_question(session, next_concept)
        session.state = state
        self.db.commit()
        out = self._state(session)
        out.last_reveal = reveal
        return out

    def _quiz_reveal(
        self, question: DiagnosticQuestion, correct: bool
    ) -> "OnboardingReveal":
        """직전 퀴즈 문항의 정답(표시용) — mcq는 정답 보기, 인출형은 기대 답안."""
        from app.features.diagnostic.schemas import OnboardingReveal

        if question.qtype == "mcq":
            opts = list(question.options or [])
            ai = question.answer_index
            answer = opts[ai] if ai is not None and 0 <= ai < len(opts) else ""
        else:
            answer = question.expected_answer or ""
        return OnboardingReveal(correct=correct, correct_answer=answer)

    def _next_step(
        self, state: dict, answered_id: uuid.UUID, correct: bool
    ) -> uuid.UUID | None:
        """기반 체크 라우팅. 반환: 다음 출제 개념(없으면 진입 소진 = 종료).

        정답:
          depth 0  → 이 진입점은 밑바탕 OK. 선수 1홉 가벼운 상향 시드 후 다음 진입점.
          depth >0 → 경계 발견: 여기부터는 안다 → 위에서 틀린 것들이 갭. 다음 진입점.
        오답:
          depth < MAX → 선수 사슬로 한 단계 하강 (어디까지 모르는지).
          하강 불가(그래프 바닥) → bottom 갭 기록(에지 역주입 후보). 다음 진입점.
          depth == MAX → 하강분 전부 갭. 다음 진입점.
        """
        asked_ids = {a["concept_id"] for a in state["asked"]}
        depth = int(state.get("depth", 0))
        root = state["plan"][state["entry_idx"]]

        def wrong_chain() -> list[str]:
            return [
                a["concept_id"]
                for a in state["asked"]
                if a["root"] == root and not a["correct"]
            ]

        if correct:
            if depth > 0:
                # 하강 중 정답 = 결손 경계. 위에서 틀린 것들이 이 진입점의 갭.
                state["gaps"] = [
                    *state["gaps"],
                    {"concept_id": root, "missing": wrong_chain(), "bottom": False},
                ]
            else:
                self._seed_known_prereqs(state, answered_id)
            return self._advance_entry(state, asked_ids)

        if depth < _MAX_DEPTH:
            nxt = self.placement._first_prerequisite(answered_id, exclude=asked_ids)
            if nxt is not None:
                state["depth"] = depth + 1
                state["descents"] = int(state.get("descents", 0)) + 1
                return nxt
            # 선수 에지 없음 = 그래프 바닥에서 오답 → 역주입 후보
            state["gaps"] = [
                *state["gaps"],
                {"concept_id": root, "missing": wrong_chain(), "bottom": True},
            ]
            return self._advance_entry(state, asked_ids)

        state["gaps"] = [
            *state["gaps"],
            {"concept_id": root, "missing": wrong_chain(), "bottom": False},
        ]
        return self._advance_entry(state, asked_ids)

    def _advance_entry(self, state: dict, asked_ids: set[str]) -> uuid.UUID | None:
        state["depth"] = 0
        idx = int(state["entry_idx"]) + 1
        while idx < len(state["plan"]):
            candidate = state["plan"][idx]
            if candidate not in asked_ids:
                state["entry_idx"] = idx
                return uuid.UUID(candidate)
            idx += 1
        state["entry_idx"] = idx
        return None

    def _record_mastery(
        self, state: dict, question: DiagnosticQuestion, correct: bool
    ) -> None:
        """응답을 사용자 단위 ConceptMastery(BKT)에 기록 — 인출 데이터 재활용 원칙.

        이 strength가 곧 씨앗: 학습 루프의 선행 결손 판정·bridge 결정이 소비한다.
        """
        user_id = uuid.UUID(state["user_id"])
        mastery = self.db.get(ConceptMastery, (user_id, question.concept_id))
        if mastery is None:
            mastery = ConceptMastery(
                user_id=user_id,
                concept_id=question.concept_id,
                session_id=question.session_id,
                strength=settings.BKT_P_INIT,
                answered_count=0,
            )
            self.db.add(mastery)
        else:
            mastery.session_id = question.session_id
        mastery.strength = bkt.update(
            mastery.strength, correct=correct, params=self.diag._params(question.qtype)
        )
        mastery.answered_count = (mastery.answered_count or 0) + 1
        mastery.resolved = True
        self.db.flush()

    def _seed_known_prereqs(self, state: dict, concept_id: uuid.UUID) -> None:
        """진입점 정답 → 직접 선수 1홉에 가벼운 상향 시드(경계 확장은 안 함)."""
        user_id = uuid.UUID(state["user_id"])
        for pid in self.diag.repo.get_prerequisite_ids(concept_id):
            row = self.db.get(ConceptMastery, (user_id, pid))
            if row is None:
                row = ConceptMastery(
                    user_id=user_id, concept_id=pid,
                    strength=_KNOWN_PREREQ_STRENGTH, answered_count=0,
                )
                self.db.add(row)
            else:
                row.strength = max(row.strength, _KNOWN_PREREQ_STRENGTH)
        self.db.flush()

    # ── 종료: 프로파일 확정 + 시딩 + 갭 기록 + 역주입 ─────────────
    async def _complete(
        self, session: DiagnosticSession, state: dict
    ) -> OnboardingState:
        from app.features.profile import repository as profile_repo
        from app.features.profile.logic import profile_label
        from app.features.seed.service import SeedService

        user_id = uuid.UUID(state["user_id"])

        # [1] 성향 프로파일 — 고정 문항 + 프로브 관찰 신호
        events = [
            {"source": "onboarding", "axis": a["axis"], "signal": a["signal"]}
            for a in state.get("disp_answers", [])
        ]
        probe = state.get("probe") or {}
        if probe.get("choice") is not None:
            events.append(
                {
                    "source": "probe",
                    "axis": "representation",
                    "signal": 1.0 if probe["choice"] == 0 else 0.0,
                }
            )
        profile_row = profile_repo.append_events(self.db, user_id=user_id, events=events)
        label, traits = profile_label(profile_row.axes)

        # [2] 에지 역주입 — 그래프 바닥에서 오답이 난 진입점에 한해, 상한 2
        injected = await self._inject_missing_prereqs(session.course_id, state, user_id)

        # [3] 세션 종료 + 씨앗 확정 (전 절 todo — 아무것도 잠그지 않는다)
        self.diag.repo.complete_session(session)
        seed = SeedService(self.db)
        summary = seed.finalize_onboarding(
            session.course_id,
            user_id=user_id,
            foundation={
                "probed": [
                    {"concept_id": a["concept_id"], "correct": a["correct"],
                     "depth": a["depth"]}
                    for a in state.get("asked", [])
                ],
                "gaps": state.get("gaps", []),
                "injected": [str(c.id) for c in injected],
            },
            diag_q_count=len(state.get("asked", [])),
            purpose=state.get("purpose") or "exam",
        )

        gap_outs: list[FoundationGapOut] = []
        for gap in state.get("gaps", []):
            concept = self.db.get(Concept, uuid.UUID(gap["concept_id"]))
            missing_names = [
                c.name
                for cid in gap.get("missing", [])
                if (c := self.db.get(Concept, uuid.UUID(cid))) is not None
            ]
            if concept is not None:
                gap_outs.append(
                    FoundationGapOut(
                        concept_id=concept.id,
                        concept_name=concept.name,
                        missing=missing_names,
                    )
                )

        _log.info(
            "온보딩 종료: course %s — 내용 %d문항, 갭 %d, 역주입 %d, 시딩 %d",
            session.course_id, len(state.get("asked", [])),
            len(gap_outs), len(injected), summary.get("seeded", 0),
        )
        return OnboardingState(
            session_id=session.id,
            phase="done",
            step=self._step_of(state),
            total_steps=self._total_of(state),
            done=True,
            result=OnboardingResult(
                label=label,
                traits=traits,
                axes=dict(profile_row.axes or {}),
                foundation_gaps=gap_outs,
                injected_prereqs=[c.name for c in injected],
                seeded=summary.get("seeded", 0),
            ),
        )

    async def _inject_missing_prereqs(
        self, course_id: uuid.UUID, state: dict, user_id: uuid.UUID
    ) -> list[Concept]:
        """브리프 §3-2 '그래프 역주입': 선수 에지가 아예 없는데 오답이 난 진입점에
        LLM으로 선수 개념 1개 + prerequisite 에지를 만든다. 상한으로 오염 방지."""
        from app.core.llm.solar import solar_client

        bottoms = [g for g in state.get("gaps", []) if g.get("bottom")][:_INJECT_CAP]
        injected: list[Concept] = []
        for gap in bottoms:
            root = self.db.get(Concept, uuid.UUID(gap["concept_id"]))
            if root is None:
                continue
            try:
                raw = await solar_client.generate_json(
                    f"개념 '{root.name}'({root.description or ''})을 이해하기 위해 "
                    "먼저 알아야 할 가장 직접적인 선수 개념 1개를 제시하라. "
                    "교과서 수준의 표준 개념이어야 한다.\n"
                    '출력 JSON: {"name": str, "description": "2문장 설명"}',
                    system="너는 커리큘럼 설계자다. 출력은 지정한 JSON 스키마만 따른다.",
                )
                name = str(raw.get("name") or "").strip()
                description = str(raw.get("description") or "").strip()
                if not name:
                    continue
            except Exception as exc:  # noqa: BLE001 — 역주입은 보조, 실패 무시
                _log.warning("선수 역주입 생성 실패: %s", exc)
                continue
            concept = Concept(
                course_id=course_id,
                name=name[:512],
                description=description or None,
                source="ai_prereq",
                depth_level=(root.depth_level or 0) + 1,
            )
            self.db.add(concept)
            self.db.flush()
            self.db.add(
                ConceptEdge(
                    from_concept_id=root.id,
                    to_concept_id=concept.id,
                    kind="prerequisite",
                )
            )
            # 결손으로 판정된 선수 — 낮은 strength 시드(학습 루프가 브리지 삽입)
            self.db.add(
                ConceptMastery(
                    user_id=user_id, concept_id=concept.id,
                    strength=0.1, answered_count=0,
                )
            )
            self.db.flush()
            injected.append(concept)

        if injected:
            # ai_prereq는 외부 근거가 있어야 JIT 생성 게이트를 통과한다.
            from app.features.seed.refs import collect_external_refs

            try:
                await collect_external_refs(self.db, course_id)
            except Exception as exc:  # noqa: BLE001
                _log.warning("역주입 개념 외부근거 수집 실패(후속 재시도 가능): %s", exc)
        return injected

    # ── 상태 직렬화 ───────────────────────────────────────────
    def _step_of(self, state: dict) -> int:
        done_disp = int(state.get("disp_idx", 0))
        done_probe = 1 if (state.get("probe") or {}).get("choice") is not None else 0
        done_quiz = len(state.get("asked", []))
        return done_disp + done_probe + done_quiz + 1

    def _total_of(self, state: dict) -> int:
        # 성향 4 + 프로브 1 + (진입점 수 + 지금까지의 하강 수, 내용 상한 캡)
        content = min(
            _MAX_CONTENT_QUESTIONS,
            len(state.get("plan", [])) + int(state.get("descents", 0)),
        )
        return len(_DISPOSITION_ITEMS) + 1 + content

    def _state(self, session: DiagnosticSession) -> OnboardingState:
        state = session.state or {}
        phase = state.get("phase", "disposition")
        base = dict(
            session_id=session.id,
            step=min(self._step_of(state), self._total_of(state)),
            total_steps=self._total_of(state),
            done=False,
        )
        if phase == "disposition":
            item = _DISPOSITION_ITEMS[int(state.get("disp_idx", 0))]
            return OnboardingState(
                phase="disposition",
                disposition=DispositionItemOut(
                    id=item["id"],
                    prompt=item["prompt"],
                    options=[label for label, _ in item["options"]],
                ),
                **base,
            )
        if phase == "probe":
            probe = state.get("probe") or {}
            concept = self.db.get(Concept, uuid.UUID(probe["concept_id"]))
            return OnboardingState(
                phase="probe",
                probe=ProbeOut(
                    concept_id=uuid.UUID(probe["concept_id"]),
                    concept_name=concept.name if concept else "",
                    variant_a=probe["variant_a"],
                    variant_b=probe["variant_b"],
                ),
                **base,
            )
        # quiz — 활성 문항 서빙
        question = self.diag.repo.get_active_question(session.id)
        if question is None:
            raise HTTPException(status_code=500, detail="활성 문항이 없습니다.")
        concept = self.db.get(Concept, question.concept_id)
        return OnboardingState(
            phase="quiz",
            question=QuestionOut(
                id=question.id,
                concept_id=question.concept_id,
                concept_name=concept.name if concept else "",
                qtype=question.qtype,  # type: ignore[arg-type]
                question=question.question,
                options=list(question.options) if question.options else [],
            ),
            **base,
        )
