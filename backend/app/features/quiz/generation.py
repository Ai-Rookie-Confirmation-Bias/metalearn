"""⑤⑥ LLM 출력 파싱 + 기계 검사 + evidence 변환. 순수 함수 (LLM 호출은 service).

기계 검사 = LLM 심판 전에 코드로 잡을 수 있는 불량을 먼저 거른다:
근거 번호 실존, cloze 정답의 원문 존재, mcq 구조 등.
"""
import json
import re

from pydantic import ValidationError

from app.features.quiz.schemas import GeneratedItem, ParsedChunk


def parse_generation_response(raw: str) -> list[GeneratedItem]:
    """LLM 응답 → 문항 목록. 스키마에 안 맞는 문항은 개별 폐기 (전체 실패 아님)."""
    data = _extract_json(raw)
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
    """심판 응답 → (합격 여부, 사유) 목록. 응답이 깨지면 전원 불합격 (보수적)."""
    data = _extract_json(raw)
    verdicts = [(False, "심판 응답 파싱 실패")] * n_items
    if not isinstance(data, list):
        return verdicts
    for entry in data:
        try:
            i = int(entry["index"])
            if 0 <= i < n_items:
                verdicts[i] = (bool(entry["pass"]), str(entry.get("reason", "")))
        except (KeyError, TypeError, ValueError):
            continue
    return verdicts


def _extract_json(raw: str):
    """응답에서 JSON을 꺼낸다. ```json fence·앞뒤 잡담 허용."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start = min((i for i in (text.find("["), text.find("{")) if i >= 0), default=-1)
    if start < 0:
        return None
    for end in range(len(text), start, -1):
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            continue
    return None


def _sentence_ids(evidence) -> list[int]:
    """["s3","s4"] 또는 [3,4] → [3,4]."""
    ids: list[int] = []
    for e in evidence or []:
        if isinstance(e, int):
            ids.append(e)
        elif isinstance(e, str) and (m := re.fullmatch(r"s?(\d+)", e.strip())):
            ids.append(int(m.group(1)))
    return ids


# ── 기계 검사 ─────────────────────────────────────────────


def mechanical_check(item: GeneratedItem, chunk: ParsedChunk) -> str | None:
    """불량 사유를 반환. None = 통과."""
    if not item.evidence_sentence_ids:
        return "근거 문장 번호 없음"
    if any(not (0 <= s < len(chunk.sentences)) for s in item.evidence_sentence_ids):
        return "존재하지 않는 문장 번호"

    evidence_norm = re.sub(
        r"\s+",
        "",
        " ".join(
            chunk.raw_text[chunk.sentences[s].start : chunk.sentences[s].end]
            for s in item.evidence_sentence_ids
        ),
    )
    d = item.data

    if item.type == "mcq":
        options = d.get("options")
        idx = d.get("answerIndex")
        if not isinstance(options, list) or len(options) < 2:
            return "mcq 선지 부족"
        if not isinstance(idx, int) or not (0 <= idx < len(options)):
            return "mcq answerIndex 불량"
        if len(set(map(str, options))) != len(options):
            return "mcq 선지 중복"
    elif item.type == "cloze":
        blanks = [s for s in d.get("segments", []) if isinstance(s, dict) and s.get("kind") == "blank"]
        if not blanks:
            return "cloze에 빈칸 없음"
        for b in blanks:
            ans = re.sub(r"\s+", "", str(b.get("answer", "")))
            if not ans or ans not in evidence_norm:
                return f"cloze 정답 '{b.get('answer')}'이 근거 문장에 없음"
    elif item.type == "shortAnswer":
        if not d.get("prompt") or not d.get("accepted"):
            return "shortAnswer prompt/accepted 누락"
    elif item.type == "trueFalse":
        if not d.get("statement") or not isinstance(d.get("answer"), bool):
            return "trueFalse statement/answer 불량"
    return None


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
