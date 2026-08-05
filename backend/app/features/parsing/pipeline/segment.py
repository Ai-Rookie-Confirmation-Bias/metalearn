"""5단계 — 조각 만들기. Solar 0회.

규칙:
  - 제목 요소가 경계
  - 문자 예산까지 인접 묶음
  - **요소는 절대 안 쪼갠다** → 표·수식의 원자성이 구조적으로 보장된다
  - 200자 미만 조각은 버린다 (목차 스텁·파트 표지)
  - removed 마킹된 요소는 건너뛴다

기존 대비 삭제한 것 — **파트 경계 병합 금지 규칙**.
4단계에서 파트를 뽑지 않으므로 불필요하고, 그 규칙을 살리려고 붙였던
"최상위 헤딩이 12종을 넘으면 규칙을 끈다" 같은 땜빵도 함께 사라진다.
경계는 7단계 목차 분류가 정한다.
"""
from __future__ import annotations

import logging

from app.features.parsing.schemas import Element, Segment

_log = logging.getLogger("uvicorn.error")

# 페이지 장식은 본문 개념과 무관한 노이즈다. 정제를 안 거친 입력 대비로
# 여기서도 한 번 더 막는다.
_SKIP_CATEGORIES = {"header", "footer", "footnote"}
_HEADING_CATEGORIES = {"heading1", "heading2", "heading3"}


def element_text(element: Element) -> str:
    content = element.get("content") or {}
    return str(content.get("markdown") or content.get("text") or "").strip()


def is_included(element: Element) -> bool:
    """이 요소가 조각 본문에 들어가는가.

    그림 위치 계산(2-b)이 조각 content의 offset을 되짚으려면 **여기와 정확히
    같은 기준**으로 걸러야 한다. 그래서 판정을 한 군데에만 둔다.
    """
    if element.get("removed") or element.get("category") in _SKIP_CATEGORIES:
        return False
    return bool(element_text(element))


# 이전 이름 유지 (모듈 내부용)
_element_text = element_text


class _Block:
    """제목 하나와 그 아래 본문. 조각의 재료다."""

    __slots__ = ("title", "texts", "el_from", "el_to", "pages")

    def __init__(self, title: str | None) -> None:
        self.title = title
        self.texts: list[str] = []
        self.el_from: int | None = None
        self.el_to: int | None = None
        self.pages: list[int] = []

    def add(self, text: str, index: int, page: int | None) -> None:
        self.texts.append(text)
        self.el_from = index if self.el_from is None else min(self.el_from, index)
        self.el_to = index if self.el_to is None else max(self.el_to, index)
        if page is not None:
            self.pages.append(page)

    @property
    def text(self) -> str:
        return "\n\n".join(self.texts).strip()


def plan_budget(
    elements: list[Element],
    max_budget: int,
    target_count: int,
    min_budget: int,
) -> int:
    """자료 두께에 맞는 조각 예산을 정한다.

    **7단계 목차는 조각을 단원에 배정하는 구조라 목차 개수 ≤ 조각 개수다.**
    그래서 얇은 자료를 큰 예산으로 자르면 조각이 몇 개 안 나오고, 목차를
    만들 재료 자체가 없어진다.

    실측(network, 43슬라이드 12,850자):
        예산 4,000 → 조각 4개  → 단원 3개(각 조각 1개, 제목이 내용과 어긋남)
        예산 1,070 → 조각 12개 → 단원을 실제로 묶을 수 있음

    두꺼운 자료는 건드리지 않는다 — pilgi는 4,000 예산으로도 14개,
    ryan은 19개가 나와 목표치를 이미 넘는다. 얇은 자료만 예산이 줄어든다.
    """
    total = sum(len(element_text(el)) for el in elements if is_included(el))
    if total <= 0:
        return max_budget
    if total // max_budget >= target_count:
        return max_budget

    budget = max(min_budget, total // target_count)
    if budget < max_budget:
        _log.info(
            "조각 예산 조정: %d → %d자 (본문 %d자 · 목표 조각 %d개) — "
            "얇은 자료라 목차를 만들 조각 수가 안 나온다",
            max_budget, budget, total, target_count,
        )
    return min(budget, max_budget)


def build(elements: list[Element], char_budget: int, min_chars: int) -> list[Segment]:
    """정제된 요소 배열 → 조각 목록.

    반환되는 조각의 element_from/to는 **입력 배열의 인덱스**다. 그림을
    조각에 매칭할 때 같은 좌표계를 써야 하므로 요소의 id 필드를 쓰지 않는다.
    """
    blocks = _split_by_heading(elements, char_budget)
    segments = _merge_to_budget(blocks, char_budget)

    substantial = [s for s in segments if s.char_count >= min_chars]
    # 문서 전체가 짧은 극단 케이스(슬라이드 몇 장)에서 전부 버려지면 안 된다.
    result = substantial or segments[:1]

    # seq를 최종 순서로 다시 매긴다 — 중간에 버려진 조각이 있어도 연속이어야
    # 목차 분류의 검산(조각 수 = 목차별 합계)이 성립한다.
    for seq, segment in enumerate(result):
        segment.seq = seq

    dropped = len(segments) - len(result)
    _log.info(
        "조각화: 요소 %d개 → 조각 %d개 (짧아서 버림 %d개, 평균 %d자)",
        len(elements), len(result), dropped,
        sum(s.char_count for s in result) // max(len(result), 1),
    )
    return result


def _split_by_heading(elements: list[Element], char_budget: int) -> list[_Block]:
    """제목 요소를 경계로 블록을 끊는다. 예산을 넘으면 요소 경계에서 이어 끊는다.

    제목만으로 끊으면, 파서가 제목을 거의 못 잡은 문서(슬라이드를 인쇄한 PDF,
    평문 PDF)에서 블록 하나가 문서 전체가 된다. 실측: 43,981자 문서가 조각
    6개로 나뉘어 평균 7,367자 — 예산 4,000의 두 배였다.

    그렇다고 요소를 쪼개지는 않는다. **경계는 항상 요소 사이**라서 표와 수식의
    원자성은 그대로 유지된다. 예산을 넘는 단일 요소는 통째로 남는다.
    """
    blocks: list[_Block] = []
    current = _Block(None)
    size = 0

    for index, element in enumerate(elements):
        if not is_included(element):
            continue
        text = element_text(element)

        is_heading = element.get("category") in _HEADING_CATEGORIES
        # 제목이거나, 이 요소를 넣으면 예산을 넘길 때 끊는다.
        if current.texts and (is_heading or size + len(text) > char_budget):
            blocks.append(current)
            # 예산 때문에 끊은 경우엔 제목을 그대로 물려준다 — 같은 절의 연속이다.
            current = _Block(None if is_heading else current.title)
            size = 0

        if is_heading:
            current.title = text.lstrip("# ").strip()[:80]

        current.add(text, index, element.get("page"))
        size += len(text)

    if current.texts:
        blocks.append(current)
    return blocks


def _merge_to_budget(blocks: list[_Block], char_budget: int) -> list[Segment]:
    """인접 블록을 문자 예산까지 묶는다. 블록 자체는 절대 쪼개지 않는다.

    예산을 넘는 단일 블록은 통째로 한 조각이 된다 — 표나 긴 수식 유도가
    중간에서 잘리는 것보다 조각이 큰 편이 낫다.
    """
    segments: list[Segment] = []
    group: list[_Block] = []
    group_size = 0

    def close() -> None:
        nonlocal group, group_size
        if not group:
            return
        pages = [p for b in group for p in b.pages]
        el_from = [b.el_from for b in group if b.el_from is not None]
        el_to = [b.el_to for b in group if b.el_to is not None]
        segments.append(
            Segment(
                seq=len(segments),
                content="\n\n".join(b.text for b in group),
                heading=group[0].title,
                element_from=min(el_from) if el_from else None,
                element_to=max(el_to) if el_to else None,
                page_from=min(pages) if pages else None,
                page_to=max(pages) if pages else None,
            )
        )
        group, group_size = [], 0

    for block in blocks:
        size = len(block.text)
        if group and group_size + size > char_budget:
            close()
        group.append(block)
        group_size += size
    close()

    return segments
