"""⑧ 출제용 정제 — 정답·해설을 제거하고 내려보낸다. 순수 함수."""


def strip_answers(item_type: str, data: dict) -> dict:
    if item_type == "mcq":
        return {"question": data.get("question"), "options": data.get("options")}
    if item_type == "trueFalse":
        return {"statement": data.get("statement")}
    if item_type == "shortAnswer":
        return {"prompt": data.get("prompt")}
    if item_type == "cloze":
        segments = []
        for s in data.get("segments", []):
            if s.get("kind") == "blank":
                segments.append({"kind": "blank"})  # 자리만 — 정답·별칭 제거
            else:
                segments.append({"kind": "text", "text": s.get("text")})
        return {"segments": segments}
    return {}
