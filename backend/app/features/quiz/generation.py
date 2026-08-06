"""⑤ LLM 생성 출력 파싱 + 조각(문장 번호) ↔ 근거 텍스트 변환.

검증 자체는 core/quality가 담당한다. 이 모듈은 quiz 고유 개념(조각·문장 번호)을
core의 입력 계약("문항 + 근거 텍스트")으로 바꿔주는 어댑터다.
"""
import re

from pydantic import ValidationError

from app.core.quality import checks as _checks
from app.core.quality import parsing as _parsing
from app.features.quiz.schemas import ChunkWorkOrder, GeneratedItem, ParsedChunk


def parse_generation_response(raw: str) -> list[GeneratedItem]:
    """LLM 응답 → 문항 목록. 스키마에 안 맞는 문항은 개별 폐기 (전체 실패 아님)."""
    data = _parsing.extract_json(raw)
    if not isinstance(data, list):
        return []
    items: list[GeneratedItem] = []
    for entry in data:
        try:
            entry["evidence_sentence_ids"] = _sentence_ids(entry.pop("evidence", []))
            items.append(GeneratedItem.model_validate(entry))
        except (ValidationError, TypeError, KeyError, AttributeError):
            continue
    return items


def parse_verification_response(raw: str, n_items: int) -> list[tuple[bool, str]]:
    """(하위 호환) 심판 응답 파싱 — core로 위임하되 단독 심판 의미(판독 불가=불합격) 유지."""
    return [
        v if v is not None else (False, "심판 응답 파싱 실패")
        for v in _parsing.parse_verdicts(raw, n_items)
    ]


def _sentence_ids(evidence) -> list[int]:
    """["s3","s4"] 또는 [3,4] → [3,4]."""
    ids: list[int] = []
    for e in evidence or []:
        if isinstance(e, int):
            ids.append(e)
        elif isinstance(e, str) and (m := re.fullmatch(r"s?(\d+)", e.strip())):
            ids.append(int(m.group(1)))
    return ids


def evidence_ids_reason(item: GeneratedItem, chunk: ParsedChunk) -> str | None:
    """quiz 고유 사전 검사: 근거 문장 번호가 실존하는가. 불량 사유 반환."""
    if not item.evidence_sentence_ids:
        return "근거 문장 번호 없음"
    if any(not (0 <= s < len(chunk.sentences)) for s in item.evidence_sentence_ids):
        return "존재하지 않는 문장 번호"
    return None


def evidence_scope_reason(item: GeneratedItem, order: ChunkWorkOrder) -> str | None:
    """근거가 선별(계획) 단계의 후보 문장을 벗어나면 차단 (QUIZ_TUNING §9-①).

    심판·풀이자는 '주어진 근거'를 전제로 판정하므로 근거 자체의 오매칭은 검증
    배터리가 구조적으로 못 잡는다 — 선별이 승인한 문장만 근거로 인정한다.
    개념 이름이 계획과 안 맞으면(LLM이 이름을 변형) 조각 내 전체 후보 합집합으로 완화.
    """
    by_name = {p.name: set(p.evidence_sentence_ids) for p in order.concept_plans}
    allowed = by_name.get(item.concept)
    if allowed is None:
        allowed = set().union(*by_name.values()) if by_name else set()
    outside = sorted(set(item.evidence_sentence_ids) - allowed)
    if outside:
        return f"근거 문장 {outside}이 선별된 후보 밖 (근거 오매칭 의심)"
    return None


def evidence_text(item: GeneratedItem, chunk: ParsedChunk) -> str:
    """문장 번호 → 근거 원문 텍스트 (core 검증기의 입력)."""
    return " ".join(
        chunk.raw_text[chunk.sentences[s].start : chunk.sentences[s].end].strip()
        for s in item.evidence_sentence_ids
        if 0 <= s < len(chunk.sentences)
    )


def mechanical_check(item: GeneratedItem, chunk: ParsedChunk) -> str | None:
    """(하위 호환) 번호 실존 검사 + core 기계 검사. 불량 사유 반환, None = 통과."""
    reason = evidence_ids_reason(item, chunk)
    if reason:
        return reason
    return _checks.mechanical_check(item.type, item.data, evidence_text(item, chunk))


def resolve_evidence(item: GeneratedItem, chunk: ParsedChunk) -> dict:
    """문장 번호 → offset 범위 + 원문 슬라이스 (저장 직전 변환, docs/QUIZ.md §2-⑦)."""
    ids = sorted(set(item.evidence_sentence_ids))
    ranges = [[chunk.sentences[s].start, chunk.sentences[s].end] for s in ids]
    text = " ".join(chunk.raw_text[s:e].strip() for s, e in ranges)
    return {
        "chunkIndex": chunk.index,
        "sentenceRanges": ranges,
        "text": text,
        "pageFrom": chunk.page_from,
        "pageTo": chunk.page_to,
    }
