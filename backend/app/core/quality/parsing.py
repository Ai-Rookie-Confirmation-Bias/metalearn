"""LLM 응답 파싱 — 깨진 응답은 보수적으로(불합격 쪽으로) 처리한다."""
import json
import re


def extract_json(raw: str):
    """응답에서 JSON을 꺼낸다.

    ```json fence·앞뒤 잡담·토큰 한도로 잘린 배열·객체 이어붙임 허용.
    이어붙임(`{...}{...}`)은 solar-pro3 실측 형태다 — 배열로 달라고 해도
    객체를 나열해 답한다. 최장 유효 접두사만 취하면 첫 객체 하나가 되므로,
    뒤에 완결된 객체가 더 있으면 전부 건져 배열로 돌려준다.
    """
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start = min((i for i in (text.find("["), text.find("{")) if i >= 0), default=-1)
    if start < 0:
        return None
    for end in range(len(text), start, -1):
        try:
            parsed = json.loads(text[start:end])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and text.find("{", end) != -1:
            salvaged = _salvage_objects(text[start:])
            if salvaged and len(salvaged) > 1:
                return salvaged
        return parsed
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


# json_object 강제 시 프롬프트가 요구하는 래퍼 키 (프롬프트와 계약)
_WRAPPER_KEYS = ("items", "verdicts", "answers", "revisions")


def _as_list(data):
    """dict 응답을 배열로 정규화.

    - `{"items":[...]}` 같은 래퍼 — response_format=json_object는 최상위가
      객체여야 해서 프롬프트가 배열을 래퍼 키에 담게 한다
    - 래퍼 키가 아니라도 리스트 값이 정확히 하나면 그걸 취한다 (키 이름 변형 대비)
    - 그 외 dict는 1원소 배열로 (문항 1개 배치에 `{...}`로 답하는 pro3 실측)
    """
    if not isinstance(data, dict):
        return data
    for key in _WRAPPER_KEYS:
        if isinstance(data.get(key), list):
            return data[key]
    list_values = [v for v in data.values() if isinstance(v, list)]
    if len(list_values) == 1 and all(isinstance(e, dict) for e in list_values[0]):
        return list_values[0]
    return [data]


def extract_list(raw: str) -> list | None:
    """응답에서 객체 배열을 꺼낸다 — extract_json + 래퍼/단일 객체 정규화."""
    data = _as_list(extract_json(raw))
    return data if isinstance(data, list) else None


def parse_verdicts(raw: str, n_items: int) -> list[tuple[bool, str] | None]:
    """심판 응답 → 문항별 (합격, 사유) 또는 None(판독 불가).

    None의 해석은 호출자 몫 — 단독 심판은 보수적으로 불합격 처리하고,
    배심원단의 2차 심판은 기권으로 처리한다 (validator 참조).
    """
    data = extract_list(raw)
    verdicts: list[tuple[bool, str] | None] = [None] * n_items
    if not isinstance(data, list):
        return verdicts
    for pos, entry in enumerate(data):
        try:
            # 모델이 index를 빼먹는 경우(K-EXAONE 실측) 위치로 대응
            i = int(entry.get("index", pos))
            if 0 <= i < n_items:
                verdicts[i] = (bool(entry["pass"]), str(entry.get("reason", "")))
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    return verdicts


def parse_solutions(raw: str, n_items: int) -> list:
    """풀이자 응답 → 문항별 답 목록 (없으면 None — check_solution이 불합격 처리)."""
    data = extract_list(raw)
    answers: list = [None] * n_items
    if not isinstance(data, list):
        return answers
    for pos, entry in enumerate(data):
        try:
            i = int(entry.get("index", pos))
            if 0 <= i < n_items:
                answers[i] = entry.get("answer")
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    return answers


def parse_revisions(raw: str, n_items: int) -> list[dict | None]:
    """수정 응답 → 문항별 새 data (없으면 None = 수정 포기)."""
    data = extract_list(raw)
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
