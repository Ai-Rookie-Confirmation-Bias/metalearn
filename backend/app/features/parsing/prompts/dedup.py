"""10단계 중복 판정 프롬프트.

유사도로는 후보만 모으고 **판정은 LLM이 한다.** 실측상 진짜 중복이
0.85~0.92 구간에 별개 개념과 섞여 분포해서, 문턱 하나로는 절대 못 가른다.
0.90에서 자르면 중복을 놓치고, 0.86에서 자르면 '전위 순회'와 '후위 순회'가
같은 개념이 되어 버린다.
"""
from __future__ import annotations

SYSTEM = (
    "너는 지식 그래프의 중복 개념 판정기다. "
    "출력은 반드시 지정한 JSON 스키마만 따른다."
)

# 정의 미리보기 길이. 이름만으로는 상하위 관계를 못 가른다.
DEFINITION_CHARS = 90


def build_prompt(pairs: list[tuple[str, str, str, str, float]]) -> str:
    """pairs: [(A이름, A정의, B이름, B정의, 유사도), ...]"""
    lines = [
        "아래 개념 쌍들이 '완전히 같은 개념의 다른 표기'인지 판정하라.\n\n",
        "같음(병합)으로 판정:\n",
        "  - 띄어쓰기·기호 차이 (일계도함수 / 일계 도함수)\n",
        "  - 약어와 전체 명칭 (DRM / 디지털 저작권 관리)\n",
        "  - 완전 동의어 표기 (이진 탐색 트리 / 이진 검색 트리)\n\n",
        "다름으로 판정:\n",
        "  - 포함·상하위 관계 (테스트 드라이버 / 드라이버)\n",
        "  - 인접·대비 개념 (전위 순회 / 후위 순회, DAC / MAC)\n",
        "  - 속성·범위가 다른 세부 변형 (/24 서브넷 / /31 서브넷)\n",
        "  - **애매하면 다름으로.** 잘못 합치면 원문 두 곳이 한 개념에 "
        "뭉뚱그려져 복구가 어렵다.\n\n",
        '출력 JSON: {"same": [같은 쌍의 번호, ...]}\n\n',
    ]
    for i, (a_name, a_def, b_name, b_def, _sim) in enumerate(pairs):
        lines.append(
            f"[{i}] A: {a_name} — {(a_def or '')[:DEFINITION_CHARS]}\n"
            f"    B: {b_name} — {(b_def or '')[:DEFINITION_CHARS]}\n"
        )
    return "".join(lines)
