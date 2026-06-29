"""[2.DTO] Pydantic 입출력 타입 및 유효성 검증."""
import uuid
from typing import Literal

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    topic: str


class GenerateResponse(BaseModel):
    content: str


# --- 튜터 세션 ---

TutorStepType = Literal["question", "hint_1", "hint_2", "answer_reveal"]
SessionStatus = Literal["active", "completed"]
SessionType = Literal["pdf_concept", "prerequisite"]


class StartSessionRequest(BaseModel):
    profile_id: uuid.UUID
    unit_order: int = Field(ge=1)


class StartSessionResponse(BaseModel):
    session_id: uuid.UUID
    question: str


class StartPrerequisiteResponse(BaseModel):
    session_id: uuid.UUID
    prereq_concept_title: str
    why: str
    question: str
    depth: int
    is_foundational: bool


class RespondRequest(BaseModel):
    user_response: str = Field(min_length=1)


class RespondCorrectResponse(BaseModel):
    correct: Literal[True] = True
    feedback: str


class RespondIncorrectResponse(BaseModel):
    correct: Literal[False] = False
    hint: str
    missing_concept: str
    reason: str


class WeaknessEntry(BaseModel):
    concept_id: str
    missing_concept: str = ""
    reason: str = ""


class HintResponse(BaseModel):
    step_type: TutorStepType
    content: str


class CompleteSessionResponse(BaseModel):
    concept_id: str
    resolved: bool
    current_weaknesses: list[WeaknessEntry]
    return_to_session_id: uuid.UUID | None = None
