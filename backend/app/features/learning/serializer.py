"""[3.Service] 봉투 직렬화 — DB Block → 프론트 봉투(BlockEnvelope).

여기서 두 가지 서빙 규칙을 강제한다:

1. 정답 스트립(치팅 방지): 판단은 전부 서버(기획서 §8 경계). data에 든 정답류
   필드는 와이어에 싣지 않는다. type별 스트립 규칙은 _STRIP_FIELDS 단일 관리.
     - mcq         : answerIndex, explanation 제거
     - cloze       : text+blanks → segments[](text/blank 교차, 정답 없는 blank)로 변환
     - explainBack : rubric 제거(채점 기준 노출 금지)
     - reviewGate  : rubric 제거
   ※ 새 type 추가 시 여기에 규칙을 등록해야 한다(등록 없으면 data 원본 그대로).
   ※ 채점 **후** 정답/해설은 POST /attempts 응답의 reveal로 공개(유출 아님).

2. variant 필터(§6 확신도 스킵) — 팀 미결(blocks.variant 컬럼) 전까지의 잠정
   구현으로 '부분집합(㉮)' 방식을 쓴다:
     - full       : 전부
     - compressed : analogy(발판 비유) 제외 — 아는 사람에게 비유는 소음
     - quick      : tracked 문제 블록만 — 확인 인출만 하고 통과
   ㉯(variant별 별도 생성)로 확정되면 이 필터를 blocks.variant 조회로 교체한다.
"""
from __future__ import annotations

from app.core.enums import ServeVariant
from app.features.learning.models import Block
from app.features.learning.schemas import BlockEnvelope, BlockMeta, ExternalRefOut
from app.features.seed.models import ExternalRef

# type → data에서 제거할 정답류 필드
_STRIP_FIELDS: dict[str, set[str]] = {
    "mcq": {"answerIndex", "explanation"},
    "cloze": {"blanks"},
    "explainBack": {"rubric"},
    "reviewGate": {"rubric"},
}


_CLOZE_MARKER = "{{blank}}"


def _cloze_to_segments(data: dict) -> dict:
    """cloze `text`(+`{{blank}}`) → 프론트 계약 `segments[]`(text/blank 교차, 정답 제거).

    blank 세그먼트엔 정답을 싣지 않는다(서버 채점). 프론트는 blank마다 입력칸을 렌더하고
    입력을 순서대로 모아 POST /attempts로 보낸다.
    """
    text = data.get("text") or ""
    parts = text.split(_CLOZE_MARKER)
    segments: list[dict] = []
    for i, part in enumerate(parts):
        if part:
            segments.append({"kind": "text", "text": part})
        if i < len(parts) - 1:
            segments.append({"kind": "blank"})
    out: dict = {"segments": segments}
    if data.get("title"):
        out["title"] = data["title"]
    return out


def strip_answers(btype: str, data: dict) -> dict:
    """서빙용 data 사본 생성(원본 불변). 정답 필드를 제거한다."""
    if btype == "cloze":
        return _cloze_to_segments(data)
    fields = _STRIP_FIELDS.get(btype)
    if not fields:
        return dict(data)
    return {k: v for k, v in data.items() if k not in fields}


# variant → 블록 포함 여부 판정
def _include_in_variant(block: Block, variant: str) -> bool:
    if variant == ServeVariant.QUICK:
        return block.tracked
    if variant == ServeVariant.COMPRESSED:
        return block.type != "analogy"
    return True  # full


def filter_by_variant(blocks: list[Block], variant: str) -> list[Block]:
    picked = [b for b in blocks if _include_in_variant(b, variant)]
    # quick/compressed에서 전부 걸러지면(예: 문제 블록이 없음) full로 안전 폴백
    return picked if picked else list(blocks)


def to_envelope(
    block: Block, *, external_refs: dict | None = None
) -> BlockEnvelope:
    """DB Block → 와이어 봉투. external_refs: {id: ExternalRef} (ai_prereq 인용 배지)."""
    refs: list[ExternalRefOut] = []
    if block.external_ref_ids and external_refs:
        for rid in block.external_ref_ids:
            r: ExternalRef | None = external_refs.get(rid)
            if r is not None:
                refs.append(ExternalRefOut(title=r.title, url=r.url, kind=r.source_kind))

    meta = block.meta or {}
    return BlockEnvelope(
        id=str(block.id),
        type=block.type,
        kind=block.kind,
        concept_id=str(block.concept_id) if block.concept_id else None,
        source=block.source,
        source_chunk_ids=[str(c) for c in (block.source_chunk_ids or [])],
        external_refs=refs,
        verified=block.verified,
        tracked=block.tracked,
        data=strip_answers(block.type, block.data or {}),
        meta=BlockMeta(
            difficulty=meta.get("difficulty", "mid"),
            version=meta.get("version", 1),
        ),
    )
