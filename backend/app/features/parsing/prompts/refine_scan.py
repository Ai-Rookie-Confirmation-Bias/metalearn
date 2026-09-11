"""4단계 정제 2층 프롬프트 — 본문 시작 지점 하나만 묻는다.

기존 구현은 세 가지를 물었다: ① 본문 시작 ② 문서 프로파일 ③ **파트 경계**.

③을 버렸다. 파트 경계 판정이 가드레일 5개를 달고도 자주 틀렸고, 실패하면
챕터가 파일명 하나로 퇴화하던 지점이다. **7단계 목차 분류가 대체한다.**
②도 버렸다 — v1에서 저장만 하고 아무도 안 썼다.

남은 건 ①뿐이다. 표지·저자 인사말·구매 안내를 걷어내는 용도.
규칙 정제(3단계)로는 이것들을 못 잡는다 — 기계가 확신할 수 있는 패턴이 없다.
"""
from __future__ import annotations

from collections import Counter

from app.features.parsing.schemas import Element

SYSTEM = (
    "너는 학습 자료 문서의 구조를 판정하는 분석기다. "
    "출력은 반드시 지정한 JSON 스키마만 따른다. "
    "본문 내용을 생성하거나 고쳐 쓰지 말고, 요소 번호로만 답한다."
)

HEAD_ELEMENTS = 40      # 앞부분 원문을 보여줄 요소 수
HEAD_TEXT_CHARS = 200   # 요소당 원문 절단 길이


def build_prompt(elements: list[Element], element_text) -> str:
    head = [
        f"{i} [{el.get('category')}]: {element_text(el)[:HEAD_TEXT_CHARS]}"
        for i, el in enumerate(elements[:HEAD_ELEMENTS])
        if not el.get("removed")
    ]
    stats = Counter(str(el.get("category")) for el in elements)

    return (
        "학습 자료 문서를 파서가 요소 배열로 분해했다. "
        "아래는 문서 통계와 앞부분 요소들의 원문이다.\n"
        f"문서 통계: 총 {len(elements)}요소 — "
        f"수식 {stats.get('equation', 0)}, 표 {stats.get('table', 0)}, "
        f"문단 {stats.get('paragraph', 0)}, 그림 {stats.get('figure', 0)}\n\n"
        "실제 학습 본문이 시작되는 요소 번호를 판정하라.\n"
        "규칙:\n"
        "1. 비학습 콘텐츠는 오직 다음뿐이다 — 표지, 저자 인사말, 목차, "
        "저작권 고지, 구매·수강 안내.\n"
        "2. 주의: '준비 학습', '생각 열기', 연습 문제, 그리고 수식·표·"
        "그래프가 들어 있는 요소는 **학습 본문이다.** 절대 비학습으로 "
        "분류하지 말 것.\n"
        "3. 애매하면 본문 시작을 앞당겨라 — 덜 지우는 쪽이 안전하다. "
        "문서가 처음부터 본문이면 0.\n\n"
        'JSON 형식: {"body_start_element": int}\n\n'
        "=== 앞부분 요소 원문 ===\n" + "\n".join(head)
    )
