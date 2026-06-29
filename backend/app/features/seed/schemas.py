"""[2.DTO] seed 설문·진단·슬라이스."""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


LearningGoal = Literal["exam", "concept_understanding", "problem_solving", "skim"]


class LearningRange(BaseModel):
    start: str = Field(description="chapter_id 또는 concept_id")
    end: str


class SurveyRequest(BaseModel):
    document_id: uuid.UUID
    learning_range: LearningRange
    learning_goal: LearningGoal | None = None


class SeedProfileResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    learning_range: LearningRange
    learning_goal: str | None
    concepts_in_range: list[str]
    weaknesses: list[str]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DiagnosticQuestionPublic(BaseModel):
    id: uuid.UUID
    concept_id: str
    question_text: str
    options: list[str]

    model_config = {"from_attributes": True}


class DiagnosticSessionResponse(BaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    status: str
    questions: list[DiagnosticQuestionPublic]
    generation_mode: Literal["llm", "fallback"] = "fallback"
    generation_note: str | None = None


class AnswerItem(BaseModel):
    question_id: uuid.UUID
    choice_index: int


class SubmitDiagnosticRequest(BaseModel):
    answers: list[AnswerItem]


class DiagnosticResultResponse(BaseModel):
    session_id: uuid.UUID
    profile_id: uuid.UUID
    weaknesses: list[str]
    score: float
    status: str


class SeedSlice(BaseModel):
    document_id: uuid.UUID
    profile_id: uuid.UUID
    learning_range: LearningRange
    learning_goal: str | None
    concepts_in_range: list[str]
    weaknesses: list[str]


class PrerequisiteSuggestion(BaseModel):
    id: str
    label: str
    source: Literal["in_document", "external"]
    reason: str
    recommended: bool = False


class PrerequisiteAnalysis(BaseModel):
    suggestions: list[PrerequisiteSuggestion]
    concepts_needing_prereq: list[str] = Field(default_factory=list)
    summary: str = ""
    generation_mode: Literal["llm", "local"] = "local"
    generation_note: str | None = None


class PrerequisiteAnalyzeRequest(BaseModel):
    document_id: uuid.UUID
    learning_range: LearningRange


class CurriculumUnit(BaseModel):
    order: int
    concept_id: str
    title: str
    page_numbers: list[int]
    chunk_ids: list[str]
    chapter_id: str | None
    priority: Literal["weakness", "standard"]
    status: Literal["pending", "in_progress", "completed"] = "pending"
    summary: str | None = None
    focus: str | None = None
    content: str | None = None  # Solar가 생성한 마크다운 학습 콘텐츠
    is_verified: bool | None = None  # groundedness 검증 통과 여부


class CurriculumChapterGroup(BaseModel):
    chapter_id: str | None
    chapter_title: str
    units: list[CurriculumUnit]


class CurriculumResponse(BaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    document_id: uuid.UUID
    learning_goal: str | None
    weakness_count: int
    total_units: int
    units: list[CurriculumUnit]
    chapter_groups: list[CurriculumChapterGroup]
    generation_mode: Literal["llm", "local"] = "local"
    generation_note: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
