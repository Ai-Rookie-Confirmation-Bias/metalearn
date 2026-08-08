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
    """LLM 응답 → 문항 목록. 스키마에 안 맞는 문항은 개별 폐기 (전체 실패 아님).

    `{"items":[...]}` 래퍼·단일 객체·이어붙임 전부 extract_list가 정규화한다."""
    data = _parsing.extract_list(raw)
    if data is None:
        return []
    items: list[GeneratedItem] = []
    for entry in data:
        try:
            # pro3 편차: evidence를 최상위가 아니라 data 안에 넣는 경우가 있다
            # (17회차 실측 — "근거 문장 번호 없음"으로 억울 폐기되던 패턴)
            if "evidence" not in entry and isinstance(entry.get("data"), dict):
                if "evidence" in entry["data"]:
                    entry["evidence"] = entry["data"].pop("evidence")
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


def build_cloze_segments(item: GeneratedItem, chunk: ParsedChunk) -> str | None:
    """cloze 픽(문장 번호+정답 용어) → segments 조립. 불량 사유 반환, None = 성공.

    pro3 네이티브 재구성 ① (QUIZ_TUNING §12): LLM은 "어느 문장에서 어떤 용어를
    비울지"만 고르고, 지문 자르기·빈칸 뚫기·정답 노출 방지는 코드가 결정적으로
    한다. pro3의 cloze 구조 불량(원문 통째+빈칸 덧붙임·정답 노출·기호 빈칸)을
    생성 단계에서 원천 제거. 구형 segments 응답은 그대로 통과(기존 검사 경로).
    """
    d = item.data
    if "segments" in d:
        return None  # 이미 조립된 형태 — 기존 기계 검사가 판정

    answer = str(d.get("answer", "")).strip()
    if not answer:
        return "cloze 정답 용어 없음"

    sids = _sentence_ids([d.get("sentence")]) if d.get("sentence") is not None else []
    sid = sids[0] if sids else (
        item.evidence_sentence_ids[0] if item.evidence_sentence_ids else None
    )
    if sid is None or not (0 <= sid < len(chunk.sentences)):
        return "cloze 빈칸 문장 번호 불량"

    anchor = chunk.sentences[sid]
    sentence = chunk.raw_text[anchor.start : anchor.end].strip()
    count = sentence.count(answer)
    if count == 0:
        return f"cloze 정답 '{answer}'이 지정 문장에 글자 그대로 없음"
    if count > 1:
        return f"cloze 정답 '{answer}'이 문장에 {count}번 등장 (빈칸 위치 모호)"

    before, _, after = sentence.partition(answer)
    aliases = [str(a) for a in d.get("aliases", []) if str(a).strip()]
    segments: list[dict] = []
    if before.strip():
        segments.append({"kind": "text", "text": before})
    segments.append({"kind": "blank", "answer": answer, "aliases": aliases})
    if after.strip():
        segments.append({"kind": "text", "text": after})
    if len(segments) < 2:
        return "cloze 지문이 빈칸뿐 (문장 전체가 정답)"

    item.data = {"segments": segments}
    # 빈칸 문장은 근거에 포함시킨다 (근거 표시·검증이 이 문장을 봐야 함)
    if sid not in item.evidence_sentence_ids:
        item.evidence_sentence_ids = sorted({*item.evidence_sentence_ids, sid})
    return None


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
