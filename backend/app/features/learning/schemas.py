"""[2.DTO] 학습/커리큘럼 입출력 + LLM 생성 스키마.

커리큘럼 블록은 인출(Retrieval) 설계를 강제한다:
  prose    최소 스캐폴딩 설명(빈칸 포함 가능)
  cloze    빈칸 인출 — 학습자가 직접 채운다
  inverse  역질문 — 학습자가 직접 떠올려 답한다
정답(answer)은 페이로드에 포함하되 클라이언트가 '인출 후 공개'로 가린다.
"""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter


# ── 기존 데모(generate) ──────────────────────────────────────────────
class GenerateRequest(BaseModel):
    topic: str


class GenerateResponse(BaseModel):
    content: str


# ── 커리큘럼 요청 ────────────────────────────────────────────────────
class CurriculumRequest(BaseModel):
    concept_id: int
    # 진단 세션이 있으면 그 숙련도를 점수로 사용. 없으면 보수적으로 '낮음' 처리.
    session_id: int | None = None
    # 동일 개념 재요청 시 캐시 무시하고 새로 생성.
    force_regenerate: bool = False


# ── LLM 생성 블록 (판별 유니온) ──────────────────────────────────────
class ChapterBlock(BaseModel):
    """챕터 단위 이론 설명 — 문제 풀이 전 개념을 읽고 이해하는 섹션."""

    kind: Literal["chapter"]
    title: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)


class ProseBlock(BaseModel):
    kind: Literal["prose"]
    heading: str = Field(default="")
    text: str = Field(..., min_length=1)


class ClozeBlock(BaseModel):
    kind: Literal["cloze"]
    # '____' 빈칸을 포함한 문장.
    text: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)


class InverseBlock(BaseModel):
    kind: Literal["inverse"]
    prompt: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)


CurriculumBlock = Annotated[
    Union[ChapterBlock, ProseBlock, ClozeBlock, InverseBlock],
    Field(discriminator="kind"),
]


class CurriculumDraft(BaseModel):
    blocks: list[CurriculumBlock] = Field(..., min_length=1)


CURRICULUM_ADAPTER: TypeAdapter[CurriculumDraft] = TypeAdapter(CurriculumDraft)


# ── 응답 ─────────────────────────────────────────────────────────────
class CurriculumResponse(BaseModel):
    id: int
    concept_id: int
    concept_name: str
    score: float
    mode: str  # 'focused' | 'bridge'
    prerequisite_ratio: float
    main_ratio: float
    prerequisite_names: list[str] = Field(default_factory=list)
    blocks: list[dict] = Field(default_factory=list)
