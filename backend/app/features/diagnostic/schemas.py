"""[2.DTO] 진단 입출력 + LLM 문항/심판 스키마.

문항은 유형(qtype) 판별 유니온으로 강제:
  mcq      4지선다 (결정론적 채점)
  cloze    빈칸 인출 (정규화 정확매칭 → LLM 심판 폴백)
  inverse  역질문 자유인출 (LLM 심판)
LLM JSON 출력은 이 스키마로 2차 검증해 할루시네이션/파싱 에러를 차단한다.
"""
from __future__ import annotations

import uuid
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter, field_validator

QuestionType = Literal["mcq", "cloze", "inverse"]


# ── LLM 문항 생성 스키마 (판별 유니온) ───────────────────────────────
class McqDraft(BaseModel):
    qtype: Literal["mcq"]
    question: str = Field(..., min_length=1)
    options: list[str] = Field(..., min_length=4, max_length=4)
    answer_index: int = Field(..., ge=0, le=3)
    explanation: str = Field(default="")

    @field_validator("options")
    @classmethod
    def _non_empty(cls, v: list[str]) -> list[str]:
        if any(not opt.strip() for opt in v):
            raise ValueError("보기에는 빈 문자열이 있을 수 없습니다.")
        return v


class ClozeDraft(BaseModel):
    qtype: Literal["cloze"]
    # '____'(언더스코어) 빈칸을 1개 포함하는 문장.
    question: str = Field(..., min_length=1)
    expected_answer: str = Field(..., min_length=1)
    acceptable_answers: list[str] = Field(default_factory=list)
    explanation: str = Field(default="")


class InverseDraft(BaseModel):
    qtype: Literal["inverse"]
    question: str = Field(..., min_length=1)
    expected_answer: str = Field(..., min_length=1)
    explanation: str = Field(default="")


QuizDraft = Annotated[
    Union[McqDraft, ClozeDraft, InverseDraft], Field(discriminator="qtype")
]
QUIZ_ADAPTER: TypeAdapter[McqDraft | ClozeDraft | InverseDraft] = TypeAdapter(QuizDraft)


# ── LLM 배치 문항 생성 스키마 ────────────────────────────────────────
class ConceptQuestionSet(BaseModel):
    """개념 1개에 대한 문항 묶음."""

    concept_name: str = Field(..., min_length=1)
    items: list[QuizDraft] = Field(..., min_length=1)


class BatchQuizResponse(BaseModel):
    """세션 시작 시 모든 개념 문항을 한 번에 받는 스키마."""

    concepts: list[ConceptQuestionSet] = Field(..., min_length=1)


class JudgeVerdict(BaseModel):
    """LLM 심판 결과 (인출형 자유서술 채점)."""

    correct: bool
    rationale: str = Field(default="")


# ── 요청 ──────────────────────────────────────────────────────────────
class StartRequest(BaseModel):
    course_id: uuid.UUID
    # 수업 생성 위저드 STEP 3의 학습 목적(exam|career|culture|hobby) — 온보딩
    # 종료 시 enrollment.purpose로 확정, JIT 생성이 스타일 지시문으로 소비.
    purpose: str | None = None


class AnswerRequest(BaseModel):
    """유형별 입력: mcq는 selected_index, cloze/inverse는 answer_text."""

    selected_index: int | None = Field(default=None, ge=0, le=3)
    answer_text: str | None = None


# ── 응답 ──────────────────────────────────────────────────────────────
class QuestionOut(BaseModel):
    """출제용(정답 비공개). options는 mcq에서만 채워진다."""

    id: uuid.UUID
    concept_id: uuid.UUID
    concept_name: str
    qtype: QuestionType
    question: str
    options: list[str] = Field(default_factory=list)


class MasteryOut(BaseModel):
    concept_id: uuid.UUID
    concept_name: str
    strength: float
    resolved: bool
    answered_count: int


class Progress(BaseModel):
    total: int
    resolved: int
    # 문항 기준 진행(UI 표시용) — total(개념 수)을 문항 수로 오해하지 않도록.
    # 기본값 0: 구버전 직렬화 데이터와의 호환 유지.
    answered_questions: int = 0  # 이번 세션에서 답변한 문항 수
    question_cap: int = 0  # 세션 총 문항 상한 (settings.DIAG_MAX_TOTAL_QUESTIONS)


class SessionState(BaseModel):
    session_id: uuid.UUID
    status: str
    done: bool
    progress: Progress
    question: QuestionOut | None = None
    masteries: list[MasteryOut] = Field(default_factory=list)


class PlacementState(BaseModel):
    """배치고사 상태 — 문항 1개씩 서빙 (ISSUE-015). done=True일 때 결과 필드 채움."""

    session_id: uuid.UUID
    done: bool
    asked: int
    max_questions: int
    question: QuestionOut | None = None
    floor_concept: uuid.UUID | None = None
    ceiling_concept: uuid.UUID | None = None
    weak_concept_ids: list[uuid.UUID] = Field(default_factory=list)
    seed: dict | None = None


# ── 온보딩 (진단 재설계 — 성향 프로파일링 + 기반지식 체크) ──────────
class DispositionItemOut(BaseModel):
    """성향 상황판단 문항(고정 상수, 즉답형 — 정답 없음)."""

    id: str
    prompt: str
    options: list[str]


class ProbeOut(BaseModel):
    """스타일 프로브 — 같은 개념을 두 방식으로 설명, 어느 쪽이 와닿는지 고른다."""

    concept_id: uuid.UUID
    concept_name: str
    variant_a: str  # 비유·예시 중심
    variant_b: str  # 정의·원리 중심


class OnboardingAnswerRequest(BaseModel):
    """단계별 입력: 성향/프로브는 choice_index, 내용 문항은 question_id + 답."""

    choice_index: int | None = Field(default=None, ge=0, le=3)
    question_id: uuid.UUID | None = None
    selected_index: int | None = Field(default=None, ge=0, le=3)
    answer_text: str | None = None


class FoundationGapOut(BaseModel):
    concept_id: uuid.UUID
    concept_name: str
    missing: list[str] = Field(default_factory=list)  # 결손 선수 개념 이름


class OnboardingResult(BaseModel):
    label: str
    traits: list[str]
    axes: dict
    foundation_gaps: list[FoundationGapOut] = Field(default_factory=list)
    injected_prereqs: list[str] = Field(default_factory=list)
    seeded: int = 0


class OnboardingReveal(BaseModel):
    """직전 기반지식 문항의 정답 공개(가벼운 피드백) — 다음 단계와 함께 내려간다."""

    correct: bool
    correct_answer: str = ""


class OnboardingState(BaseModel):
    """온보딩 진행 상태 — phase에 따라 disposition/probe/question 중 하나가 채워진다."""

    session_id: uuid.UUID
    phase: Literal["disposition", "probe", "quiz", "done"]
    step: int  # 1-based 현재 단계
    total_steps: int  # 하강으로 늘어날 수 있음(동적)
    done: bool
    disposition: DispositionItemOut | None = None
    probe: ProbeOut | None = None
    question: QuestionOut | None = None
    result: OnboardingResult | None = None
    # 직전 기반지식 문항의 정답(표시용) — quiz phase 답변 직후에만 채워진다.
    last_reveal: OnboardingReveal | None = None


class AnswerResult(BaseModel):
    is_correct: bool
    # 정답 공개: mcq는 correct_index, 인출형은 correct_answer(모범답안).
    correct_index: int | None = None
    correct_answer: str | None = None
    explanation: str
    # 오답일 때 "왜 틀렸는지" 피드백 (정답이면 None). 자유서술=심판 사유, 객관식=정답 해설.
    feedback: str | None = None
    mastery: MasteryOut
    done: bool
    progress: Progress
    next_question: QuestionOut | None = None
