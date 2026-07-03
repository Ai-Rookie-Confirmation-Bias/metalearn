"""[3.Service] JIT 블록 생성기 — 절(개념) 하나를 봉투 블록 세트로 (기획서 §2.5A).

파이프라인: [1] 근거 확보 → [2] 생성(LLM) → [3] 검증 게이트 → verified만 반환.

순수 계층: DB/ORM에 의존하지 않는다. 입력은 개념·근거 발췌 DTO, 출력은
BlockDraft 리스트. 영속(blocks INSERT)은 repository가 담당한다.

검증(§2.5A)의 현재 범위:
  - 근거 게이트(can_mark_verified)만 강제 — book은 청크 ID, ai_prereq는 외부근거 ID 필수.
  - 사실문장 대조(faithfulness LLM 콜)는 후속 작업(TODO). 인터페이스가 같아
    이 파일의 _verify() 내부만 교체하면 된다.
  - LLM 출력이 파싱 불가/전부 폐기되면 근거 발췌를 그대로 인용하는 폴백 블록을
    만든다(지어내지 않고 청크 원문 기반 → 원칙 위반 아님).
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.core.enums import ContentSource
from app.core.llm.base import LLMClient
from app.core.verify_grade import can_mark_verified
from app.features.learning.schemas import (
    AnalogyData,
    ClozeData,
    ConceptData,
    ExplainBackData,
    McqData,
    ReviewGateData,
)

# type → (data 검증 모델, 추적 대상 여부). 기획서 ①설명/②문제 분류.
_TYPE_SPECS: dict[str, tuple[type, bool]] = {
    "concept": (ConceptData, False),
    "analogy": (AnalogyData, False),
    "cloze": (ClozeData, True),
    "mcq": (McqData, True),
    "explainBack": (ExplainBackData, True),
    "reviewGate": (ReviewGateData, True),
}

_ALLOWED_DIFFICULTY = {"easy", "mid", "hard"}


@dataclass(frozen=True)
class ChunkExcerpt:
    """생성 근거로 쓰는 책 청크 발췌."""

    id: uuid.UUID
    content: str


@dataclass(frozen=True)
class ExternalRefInput:
    """ai_prereq 개념의 외부 신뢰 근거."""

    id: uuid.UUID
    title: str | None = None
    url: str | None = None
    snippet: str | None = None


@dataclass(frozen=True)
class GenerationInput:
    concept_name: str
    concept_description: str | None
    concept_source: str  # book | ai_prereq
    chunks: list[ChunkExcerpt] = field(default_factory=list)
    external_refs: list[ExternalRefInput] = field(default_factory=list)
    difficulty_hint: int = 1  # 1~3 (mastery.difficulty)


@dataclass(frozen=True)
class BlockDraft:
    """검증을 통과해 저장 가능한 블록 초안(봉투의 서버측 원형)."""

    type: str
    source: str
    tracked: bool
    verified: bool
    data: dict
    meta: dict
    source_chunk_ids: list[uuid.UUID]
    external_ref_ids: list[uuid.UUID]


def build_prompt(inp: GenerationInput) -> str:
    """블록 생성 프롬프트. 근거 발췌를 데이터로 격리하고 JSON만 요구한다."""
    difficulty_word = {1: "기초", 2: "표준", 3: "심화"}.get(inp.difficulty_hint, "표준")
    evidence_lines: list[str] = []
    if inp.concept_source == ContentSource.BOOK:
        for c in inp.chunks:
            evidence_lines.append(f"- (chunk {c.id}) {c.content[:800]}")
    else:
        for r in inp.external_refs:
            evidence_lines.append(f"- (ref {r.id}) {r.title or ''} — {(r.snippet or '')[:600]}")
    evidence = "\n".join(evidence_lines) if evidence_lines else "(근거 없음)"

    return f"""당신은 학습 콘텐츠 생성기다. 아래 근거 발췌만 사용해 블록을 생성한다.
근거에 없는 사실을 지어내지 마라. 학습자가 직접 꺼내게(인출) 하는 문제 중심으로 구성한다.

CONCEPT_NAME: {inp.concept_name}
CONCEPT_DESC: {inp.concept_description or "(없음)"}
DIFFICULTY: {difficulty_word}

[근거 발췌 — 이 내용만 사실로 사용]
{evidence}

BLOCKS_JSON 형식으로만 응답한다. 마크다운/설명 없이 JSON 하나:
{{"blocks": [
  {{"type": "concept", "difficulty": "mid", "data": {{"title": "...", "body": "...", "whyItMatters": "..."}}}},
  {{"type": "analogy", "difficulty": "easy", "data": {{"label": "비유", "text": "..."}}}},
  {{"type": "cloze", "difficulty": "mid", "data": {{"text": "... {{{{blank}}}} ...", "blanks": ["정답"], "hint": "..."}}}},
  {{"type": "mcq", "difficulty": "mid", "data": {{"question": "...", "options": ["...", "...", "...", "..."], "answerIndex": 0, "explanation": "..."}}}},
  {{"type": "explainBack", "difficulty": "hard", "data": {{"prompt": "...", "rubric": ["키포인트1", "키포인트2"]}}}}
]}}"""


def parse_llm_blocks(raw: str) -> list[dict]:
    """LLM 응답 → 블록 dict 리스트. 코드펜스/잡담 방어."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    # 첫 '{' ~ 마지막 '}' 구간만 시도(앞뒤 잡담 방어)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return []
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    blocks = payload.get("blocks")
    return blocks if isinstance(blocks, list) else []


def _coerce_block(item: dict) -> tuple[str, dict, str] | None:
    """블록 dict 1개 → (type, 검증된 data, difficulty). 규격 미달이면 None(폐기)."""
    if not isinstance(item, dict):
        return None
    btype = item.get("type")
    spec = _TYPE_SPECS.get(btype or "")
    if spec is None:
        return None
    model_cls, _ = spec
    try:
        data = model_cls.model_validate(item.get("data") or {})
    except ValidationError:
        return None
    difficulty = item.get("difficulty")
    if difficulty not in _ALLOWED_DIFFICULTY:
        difficulty = "mid"
    return btype, data.model_dump(by_alias=True, exclude_none=True), difficulty


def _verify(
    *,
    btype: str,
    data: dict,
    concept_source: str,
    chunk_ids: list[uuid.UUID],
    ref_ids: list[uuid.UUID],
) -> tuple[bool, str, list[uuid.UUID], list[uuid.UUID]]:
    """검증 게이트. 반환: (verified, block_source, source_chunk_ids, external_ref_ids).

    비유는 근거 면제(라벨 강제). 나머지는 개념 출처를 따라 근거를 단다.
    TODO(후속): 사실문장 단위 faithfulness LLM 검증을 여기에 삽입.
    """
    if btype == "analogy":
        source = ContentSource.ANALOGY.value
        ok = can_mark_verified(
            source=source, source_chunk_ids=[], external_ref_ids=[], data=data
        )
        return ok, source, [], []

    source = concept_source
    if source == ContentSource.BOOK:
        ok = can_mark_verified(
            source=source, source_chunk_ids=chunk_ids, external_ref_ids=[], data=data
        )
        return ok, source, chunk_ids, []
    ok = can_mark_verified(
        source=source, source_chunk_ids=[], external_ref_ids=ref_ids, data=data
    )
    return ok, source, [], ref_ids


def _fallback_blocks(inp: GenerationInput) -> list[dict]:
    """LLM 실패 시 폴백: 근거 원문을 그대로 인용(생성 아님)한 최소 세트."""
    if inp.concept_source == ContentSource.BOOK and inp.chunks:
        excerpt = inp.chunks[0].content[:500]
    elif inp.external_refs and inp.external_refs[0].snippet:
        excerpt = inp.external_refs[0].snippet[:500]
    else:
        return []
    return [
        {
            "type": "concept",
            "difficulty": "mid",
            "data": {
                "title": inp.concept_name,
                "body": f"[근거 발췌] {excerpt}",
            },
        },
        {
            "type": "explainBack",
            "difficulty": "mid",
            "data": {
                "prompt": f"위 발췌를 읽고 {inp.concept_name}을(를) 자신의 말로 설명해 보세요.",
                "rubric": [inp.concept_name],
            },
        },
    ]


async def generate_section_blocks(
    llm: LLMClient, inp: GenerationInput
) -> list[BlockDraft]:
    """절(개념) 하나의 블록 세트 생성. verified 통과분만 반환한다.

    기획서 §2.5A: 실패 시 재생성 1회 → 또 실패면 폐기(여기서는 근거 인용 폴백).
    """
    chunk_ids = [c.id for c in inp.chunks]
    ref_ids = [r.id for r in inp.external_refs]

    items: list[dict] = []
    for _attempt in range(2):  # 생성 1회 + 재생성 1회
        raw = await llm.generate(build_prompt(inp))
        items = parse_llm_blocks(raw)
        if items:
            break
    if not items:
        items = _fallback_blocks(inp)

    drafts: list[BlockDraft] = []
    order = 0
    for item in items:
        coerced = _coerce_block(item)
        if coerced is None:
            continue  # 규격 미달 블록 폐기
        btype, data, difficulty = coerced
        verified, source, use_chunks, use_refs = _verify(
            btype=btype,
            data=data,
            concept_source=inp.concept_source,
            chunk_ids=chunk_ids,
            ref_ids=ref_ids,
        )
        if not verified:
            continue  # 근거 없는 블록은 저장하지 않는다(서빙 금지보다 강한 폐기 정책)
        _, tracked = _TYPE_SPECS[btype]
        drafts.append(
            BlockDraft(
                type=btype,
                source=source,
                tracked=tracked,
                verified=True,
                data=data,
                meta={"difficulty": difficulty, "version": 1, "order": order},
                source_chunk_ids=use_chunks,
                external_ref_ids=use_refs,
            )
        )
        order += 1
    return drafts
