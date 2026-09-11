"""개념 이름 정규화 — 중복 방어 ①.

**공백까지 전부 제거하는 게 핵심이다.** "일계도함수"와 "일계 도함수" 같은
표면 변형은 임베딩 유사도가 0.75~0.81이라 문턱(0.92)에 절대 안 걸린다.
표면 중복은 임베딩이 아니라 정규화가 잡아야 한다.
"""
from __future__ import annotations

import re

_PAREN_RE = re.compile(r"\s*\([^)]*\)")
_SPACE_RE = re.compile(r"\s+")
# 이음표류. 공백과 같은 자리에 쓰이므로 같이 지운다.
#
# 실측(ryan): "OSI 7계층"과 "OSI-7계층"이 별개 개념으로 저장됐다. 같은 사고가
# "IP 프로토콜"/"IP-프로토콜", "전송 계층 프로토콜"/"전송-계층-프로토콜",
# "네트워크 계층 프로토콜"/"네트워크-계층-프로토콜"까지 4쌍이었다.
# LLM이 이름 자리에 슬러그를 섞어 쓰는 탓인데, 임베딩 유사도로는 안 걸린다
# (표면 변형은 정규화가 잡아야 한다는 이 모듈의 전제 그대로다).
_DASH_RE = re.compile(r"[-–—_]+")


def normalize_name(name: str) -> str:
    """괄호 보조 표기·대괄호 기호·공백·이음표 제거 + 소문자."""
    base = _PAREN_RE.sub(" ", name)
    base = base.replace("[", " ").replace("]", " ")
    base = _DASH_RE.sub("", base)
    return _SPACE_RE.sub("", base).lower()


# 이름에 글자(한글/영문/숫자)가 하나도 없으면 개념이 아니다.
_HAS_WORD_RE = re.compile(r"[0-9A-Za-z가-힣]")

# 문서 구조 단어. 개념이 아니라 원문의 소제목이다.
_STRUCTURE_WORDS = frozenset(
    """목적 특징 장점 단점 종류 방법 대상 정의 예시 개요 구성 분류 기능
    구조 원리 절차 순서 개념 내용 항목 요약 참고 주의 비고 결론""".split()
)


_HANGUL_RE = re.compile(r"^[가-힣]$")


def is_usable_concept(name: str) -> bool:
    """개념으로 저장할 만한 이름인가. 프롬프트가 새는 경우의 마지막 방어.

    실측: 연산자 기호가 통째로 개념이 됐다 — ÷(나눗셈), ∩(교집합), σ(시그마),
    ▷◁(가마), ㅡ(차집합), X(교차곱). 프롬프트로 막는 게 우선이지만 LLM 지시는
    항상 새므로 명백한 것은 코드로도 막는다.

    **판정은 괄호를 벗긴 본체로 한다.** "÷(나눗셈)"을 통째로 보면 괄호 안
    한글 때문에 멀쩡한 이름으로 보인다. 개념의 정체는 괄호 앞이다.

    애매한 건 통과시킨다 — AES·DNS·DRAM처럼 짧아도 진짜 개념이 많고,
    "큐"·"힙"처럼 한 글자짜리 개념도 있다.
    """
    core = normalize_name(name)
    if not core:
        return False
    if core in _STRUCTURE_WORDS:
        return False
    if not _HAS_WORD_RE.search(core):
        return False  # 기호만 남음 (÷, ∩, σ, ▷◁, ㅡ)
    # 한 글자는 한글 개념만 인정한다 — "큐"·"힙"은 진짜, "X"·"A"는 기호.
    if len(core) < 2 and not _HANGUL_RE.match(core):
        return False
    return True
