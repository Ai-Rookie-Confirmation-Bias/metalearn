"""유형별 서버 채점 — 순수 함수. 정답은 서버만 보유(클라 치팅 방지).

문제은행 서빙과 검증기의 풀이 왕복 검사가 같은 채점기를 쓴다
(풀이자 답을 실제 채점 규칙 그대로 판정해야 검증이 의미 있음).
"""
import re


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", str(s)).lower()


def grade(item_type: str, data: dict, user_input) -> bool:
    if item_type == "mcq":
        try:
            return int(user_input) == int(data["answerIndex"])
        except (TypeError, ValueError, KeyError):
            return False

    if item_type == "trueFalse":
        if isinstance(user_input, bool):
            return user_input == data.get("answer")
        return _norm(user_input) in ({"o", "true", "참"} if data.get("answer") else {"x", "false", "거짓"})

    if item_type == "shortAnswer":
        accepted = [_norm(a) for a in data.get("accepted", [])]
        return _norm(user_input) in accepted

    if item_type == "cloze":
        blanks = [s for s in data.get("segments", []) if s.get("kind") == "blank"]
        answers = user_input if isinstance(user_input, list) else [user_input]
        if len(answers) != len(blanks):
            return False
        for given, blank in zip(answers, blanks):
            ok = {_norm(blank.get("answer", ""))} | {_norm(a) for a in blank.get("aliases", [])}
            if _norm(given) not in ok:
                return False
        return True

    return False


def answer_payload(item_type: str, data: dict) -> dict:
    """채점 응답에 실을 정답 표시 (해설 포함)."""
    if item_type == "mcq":
        return {
            "answerIndex": data.get("answerIndex"),
            "explanation": data.get("explanation"),
        }
    if item_type == "trueFalse":
        return {"answer": data.get("answer"), "explanation": data.get("explanation")}
    if item_type == "shortAnswer":
        return {"accepted": data.get("accepted"), "explanation": data.get("explanation")}
    if item_type == "cloze":
        return {
            "answers": [
                {"answer": s.get("answer"), "aliases": s.get("aliases", [])}
                for s in data.get("segments", [])
                if s.get("kind") == "blank"
            ]
        }
    return {}


def chosen_explanation(item_type: str, data: dict, user_input, correct: bool) -> str | None:
    """오답일 때 '고른 선지' 기준 해설 (확정안 '④를 고르셨네요' UX)."""
    if correct or item_type != "mcq":
        return None
    try:
        return data.get("wrongExplanations", {}).get(str(int(user_input)))
    except (TypeError, ValueError):
        return None
