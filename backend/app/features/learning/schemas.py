"""[2.DTO] 블록 봉투 계약 (기획서 §5 / §7).

모든 콘텐츠는 동일한 JSON 봉투로 흐른다:
  { id, type, conceptId, source, sourceChunkIds, externalRefs, verified, data, meta }

- 프론트는 `type`으로 렌더러를 고르고 `data`만 채운다(컴포넌트가 HTML을 만들지 않음).
- 서버가 생성·검증·채점의 진실. `verified=true`인 봉투만 서빙된다.
- 와이어(JSON)는 camelCase. 내부 파이썬은 snake_case로 쓰고 alias로 직렬화한다.
- `data`는 type별로 모양이 다르다. 1차 5종(concept/cloze/mcq/explainBack/reviewGate)은
  아래 타입 모델로 검증하고, 그 외 확장 type은 자유 dict로 흐른다.
"""
from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(s: str) -> str:
    head, *rest = s.split("_")
    return head + "".join(w.capitalize() for w in rest)


class _CamelModel(BaseModel):
    """camelCase 직렬화 + snake_case/camelCase 양쪽 입력 허용 공통 베이스."""

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


# ── 출처 / 메타 ──────────────────────────────────────────────────────────────
BlockSource = Literal["book", "ai_prereq", "analogy"]
AttemptKind = Literal["diagnostic", "learn", "review", "connection"]
Difficulty = Literal["easy", "mid", "hard"]


class ExternalRefOut(_CamelModel):
    """ai_prereq 블록의 외부 근거 인용(🤖 배지로 렌더)."""

    title: str | None = None
    url: str | None = None
    kind: str | None = None  # web | corpus | prereq_db


class BlockMeta(_CamelModel):
    difficulty: Difficulty = "mid"
    version: int = 1


# ── type별 data 모델 (1차 5종) ───────────────────────────────────────────────
class ConceptData(_CamelModel):
    """① 설명 블록. 추적 없음. 왜 배우나(앞연결) 한 줄 포함 가능."""

    title: str
    body: str
    why_it_matters: str | None = None


class AnalogyData(_CamelModel):
    """① 비유 블록. 검증 면제, '사실 아님' 라벨 강제."""

    label: Literal["비유"] = "비유"
    text: str


class ClozeData(_CamelModel):
    """② 빈칸 블록. text의 {{}} 위치에 blanks가 순서대로 대응."""

    text: str
    blanks: list[str]
    hint: str | None = None


class McqData(_CamelModel):
    """② 객관식 블록. answerIndex는 서버 채점용(서빙 시 제외 가능)."""

    question: str
    options: list[str]
    answer_index: int | None = None
    explanation: str | None = None


class ExplainBackData(_CamelModel):
    """② 서술형 블록. rubric 키포인트로 서버가 0~1 채점."""

    prompt: str
    rubric: list[str] = Field(default_factory=list)


class ReviewGateData(_CamelModel):
    """③ 복습 게이트. 통과해야 다음 진행."""

    prompt: str
    rubric: list[str] = Field(default_factory=list)


# ── 봉투 ─────────────────────────────────────────────────────────────────────
class BlockEnvelope(_CamelModel):
    """백엔드 → 프론트: 콘텐츠 블록 1개(공통 봉투)."""

    id: str
    type: str
    concept_id: str | None = None
    source: BlockSource = "book"
    source_chunk_ids: list[str] = Field(default_factory=list)
    external_refs: list[ExternalRefOut] = Field(default_factory=list)
    verified: bool = False
    tracked: bool = False
    data: dict = Field(default_factory=dict)
    meta: BlockMeta = Field(default_factory=BlockMeta)


class SectionBlocksResponse(_CamelModel):
    """GET /sections/:id → 절의 검증된 봉투 배열."""

    section_id: str
    concept_id: str | None = None
    variant: Literal["full", "compressed", "quick"] = "full"
    blocks: list[BlockEnvelope] = Field(default_factory=list)


# ── 정답 기록 (§7) ───────────────────────────────────────────────────────────
class AttemptRequest(_CamelModel):
    """프론트 → 백엔드: onAnswer({blockId, conceptId, userInput}).

    correct는 받아도 무시한다 — 정오 판정은 서버만 한다(정답은 서빙 시 스트립됨).
    meta: 프론트 신호 통로(elapsedMs 체류시간, hintsUsed 등) → attempts.meta에 병합.
    """

    block_id: str | None = None
    concept_id: str
    kind: AttemptKind = "learn"
    type: str | None = None
    correct: bool | None = None  # (무시됨 — 하위호환용 필드)
    user_input: str | dict | int | list | None = None
    meta: dict | None = None


class ConceptStateOut(_CamelModel):
    concept_id: str
    strength: float
    status: str  # locked | todo | learning | mastered
    explanation_score: float = 0.0
    next_due_at: str | None = None


class AttemptFeedback(_CamelModel):
    missed_points: list[str] = Field(default_factory=list)
    comment: str = ""


class NextActionOut(_CamelModel):
    """채점 직후 다음 행동(살아있는 커리큘럼 신호, next_action.py).

    advance | thin_pass | supplement | prerequisite
    """

    action: str
    reason: str


class AttemptResponse(_CamelModel):
    """정답 기록 결과. explainBack이면 score/feedback 포함."""

    correct: bool | None = None
    score: float | None = None
    feedback: AttemptFeedback | None = None
    concept: ConceptStateOut
    next_action: NextActionOut | None = None


# ── JIT 생성 트리거 / 폴링 (§5) ──────────────────────────────────────────────
class GenerateTriggerResponse(_CamelModel):
    """POST /chapters/:id/generate → 트리거 결과(멱등)."""

    chapter_id: str
    gen_status: str  # pending | generating | ready | failed


class ChapterStatusResponse(_CamelModel):
    """GET /chapters/:id → 생성 상태 폴링."""

    chapter_id: str
    title: str
    origin: str  # book | prereq
    gen_status: str
    section_ids: list[str] = Field(default_factory=list)


# ── 확신도 → variant (§6) ────────────────────────────────────────────────────
class ConfidenceRequest(_CamelModel):
    confidence: Literal["sure", "ambiguous", "unknown"]


class ConfidenceResponse(_CamelModel):
    section_id: str
    confidence: str
    variant: Literal["full", "compressed", "quick"]
