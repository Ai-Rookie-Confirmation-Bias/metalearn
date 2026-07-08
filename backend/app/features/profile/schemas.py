"""[2.DTO] 성향 프로파일 입출력."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AxisOut(BaseModel):
    score: float
    confidence: float
    n: int


class ProfileOut(BaseModel):
    axes: dict[str, AxisOut]
    label: str
    traits: list[str]


class ProfileUpdateRequest(BaseModel):
    """설정 화면의 직접 수정 — 축 이름 → 0..1 점수. 수정은 confidence 0.9 고정."""

    axes: dict[str, float] = Field(..., min_length=1)
