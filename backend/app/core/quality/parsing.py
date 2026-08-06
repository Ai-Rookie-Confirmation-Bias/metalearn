"""LLM 응답 파싱 — 깨진 응답은 보수적으로(불합격 쪽으로) 처리한다."""
import json
import re


def extract_json(raw: str):
    """응답에서 JSON을 꺼낸다. ```json fence·앞뒤 잡담·토큰 한도로 잘린 배열 허용."""
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
    return _salvage_objects(text[start:])


def _salvage_objects(text: str) -> list | None:
    """잘린 배열에서 완결된 객체만 건진다 — `[{a},{b},{잘림` → [a, b].

    추론형 모델이 토큰 한도에 걸려 배열을 못 닫는 경우(K-EXAONE 실측),
    전체 무효 대신 앞쪽의 멀쩡한 판정이라도 살린다.
    """
    objects: list = []
    depth = 0
    obj_start = -1
    in_str = False
    escape = False
    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = in_str
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            if depth == 0:
                obj_start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0:
                try:
                    objects.append(json.loads(text[obj_start : i + 1]))
                except json.JSONDecodeError:
                    pass
    return objects or None


def parse_verdicts(raw: str, n_items: int) -> list[tuple[bool, str]]:
    """심판 응답 → (합격, 사유) 목록. 깨지면 전원 불합격 (보수적)."""
    data = extract_json(raw)
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


def parse_solutions(raw: str, n_items: int) -> list:
    """풀이자 응답 → 문항별 답 목록 (없으면 None — check_solution이 불합격 처리)."""
    data = extract_json(raw)
    answers: list = [None] * n_items
    if not isinstance(data, list):
        return answers
    for entry in data:
        try:
            i = int(entry["index"])
            if 0 <= i < n_items:
                answers[i] = entry.get("answer")
        except (KeyError, TypeError, ValueError):
            continue
    return answers


def parse_revisions(raw: str, n_items: int) -> list[dict | None]:
    """수정 응답 → 문항별 새 data (없으면 None = 수정 포기)."""
    data = extract_json(raw)
    revised: list[dict | None] = [None] * n_items
    if not isinstance(data, list):
        return revised
    for entry in data:
        try:
            i = int(entry["index"])
            if 0 <= i < n_items and isinstance(entry.get("data"), dict):
                revised[i] = entry["data"]
        except (KeyError, TypeError, ValueError):
            continue
    return revised
