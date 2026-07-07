"""인출형(빈칸) 자유서술 채점의 순수 로직.

부수효과 없는 정규화 매칭. LLM 심판은 서비스 계층이 담당(폴백).
"""
from __future__ import annotations

import re
import unicodedata

# 영숫자/한글/공백을 제외한 문자(구두점 등) 제거용.
_PUNCT = re.compile(r"[^0-9a-z가-힣\s]")
_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """비교용 정규화: 유니코드 NFKC → 소문자 → 구두점 제거 → 공백 압축/제거."""
    t = unicodedata.normalize("NFKC", text).strip().lower()
    t = _PUNCT.sub("", t)
    t = _WS.sub("", t)  # 공백 차이 무시(한국어 띄어쓰기 변동 흡수)
    return t


def exact_match(answer: str, expected: str, acceptable: list[str] | None = None) -> bool:
    """정규화 정확매칭. 정답 또는 허용답안 집합과 일치하면 True."""
    norm = normalize(answer)
    if not norm:
        return False
    candidates = {normalize(expected)}
    for alt in acceptable or []:
        candidates.add(normalize(alt))
    return norm in candidates
