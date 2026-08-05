"""2단계 — 그림 분리. Solar 0회.

**파싱 단계에서 그림 설명을 만들지 않는다.** 300p 교재면 그림이 30~80개인데
파싱 호출이 2배가 되고, 실제로 화면에 뜨는 건 10~20개뿐이다. 게다가 교재
그림은 대부분 주변 원문에 설명이 이미 있어 이미지를 볼 필요가 없다.

대신 공짜로 구할 수 있는 두 가지를 여기서 준비해 둔다:
  - context_text  : 그림 앞뒤 원문. 나중에 이것만으로 설명을 만들 수 있다.
  - needs_vision  : 주변 원문으로 부족한 소수만 표시. 이 5~10개만 EXAONE 비전으로.
"""
from __future__ import annotations

import base64
import logging
import re

from app.features.parsing.pipeline import segment as segment_module
from app.features.parsing.schemas import Element, FigureDraft, Segment

_log = logging.getLogger("uvicorn.error")

_FIGURE_CATEGORIES = {"figure", "chart"}
# 아이콘·불릿 수준의 초소형은 학습 자료의 그림이 아니다.
_MIN_BLOB_BYTES = 200

# context_text로 모을 앞뒤 요소 수와 총 길이 상한.
_CONTEXT_NEIGHBORS = 2
_CONTEXT_MAX_CHARS = 800
# 주변 원문이 이보다 짧으면 설명을 대신할 수 없다고 본다.
# 실측(정처기 요약노트 21개 그림): context 길이 최소 69 · 평균 280 · 최대 800자.
# 150자로 자르면 5~6개가 걸린다 — 설계 목표(전체의 소수만 비전 호출)와 맞는다.
_VISION_MIN_CONTEXT_CHARS = 150

# 캡션 접두사. "그림 1" 형식만 보면 안 된다 — 실측에서 이 교재는 캡션이
# 21개 중 0개 검출됐고, 실제로는 "[ 소프트웨어 생명주기 (V-모델) ]" 같은
# 대괄호 제목 스타일을 쓰고 있었다.
_CAPTION_PREFIXES = ("그림", "표", "도표", "fig", "figure", "table", "chart", "<그림", "[그림")
# 한 줄짜리 대괄호/꺾쇠 제목도 캡션으로 인정한다.
_CAPTION_BRACKET_RE = re.compile(r"^\s*[\[<【][^\]>】]{2,60}[\]>】]\s*$")


def _element_text(element: Element) -> str:
    content = element.get("content") or {}
    return str(content.get("markdown") or content.get("text") or "").strip()


def _neighbors_text(elements: list[Element], index: int) -> str:
    """그림 앞뒤 인접 요소의 원문을 모은다 (순수 로직, 호출 0회).

    기존 구현은 화면에 그림을 띄울 때마다 DB를 다시 뒤졌다. 요소 배열을
    손에 든 지금 한 번에 계산해 저장하는 편이 싸고 정확하다.
    """
    parts: list[str] = []
    for offset in range(-_CONTEXT_NEIGHBORS, _CONTEXT_NEIGHBORS + 1):
        if offset == 0:
            continue
        j = index + offset
        if not 0 <= j < len(elements):
            continue
        neighbor = elements[j]
        if neighbor.get("category") in _FIGURE_CATEGORIES:
            continue
        text = _element_text(neighbor)
        if text:
            parts.append(text)
    return "\n\n".join(parts)[:_CONTEXT_MAX_CHARS]


def _find_caption(elements: list[Element], index: int) -> str | None:
    """그림 바로 앞뒤 요소가 캡션 형태인지 본다."""
    for j in (index + 1, index - 1):
        if not 0 <= j < len(elements):
            continue
        text = _element_text(elements[j])
        if not text:
            continue
        head = text[:40].lower().lstrip("*_# ")
        if head.startswith(_CAPTION_PREFIXES) or _CAPTION_BRACKET_RE.match(text):
            return text[:300]
    return None


def extract(elements: list[Element]) -> list[FigureDraft]:
    """요소 배열에서 그림 크롭을 뽑아낸다.

    **부수효과**: 각 요소의 base64_encoding 키를 제거한다(pop). 이미지의 정본은
    doc_figures이고 요소 배열은 JSONB로 저장되므로, 수 MB짜리 base64를
    남겨두면 안 된다.
    """
    figures: list[FigureDraft] = []

    for i, element in enumerate(elements):
        if not isinstance(element, dict):
            continue
        b64 = element.pop("base64_encoding", None)
        if not b64 or element.get("category") not in _FIGURE_CATEGORIES:
            continue
        try:
            blob = base64.b64decode(b64)
        except Exception:  # noqa: BLE001 — 깨진 이미지는 버린다
            _log.warning("그림 디코딩 실패, 건너뜀: element %s", element.get("id"))
            continue
        if len(blob) < _MIN_BLOB_BYTES:
            continue

        category = str(element.get("category") or "figure")
        context = _neighbors_text(elements, i)
        caption = _find_caption(elements, i)

        figures.append(
            FigureDraft(
                page=int(element.get("page") or 0),
                # 요소 배열의 인덱스를 쓴다 — 조각의 element_from/to도 같은
                # 인덱스라 범위 비교가 성립한다. DP의 id 필드는 보통 인덱스와
                # 같지만 그걸 가정하면 어긋났을 때 그림이 조각에 안 붙는다.
                element_id=i,
                category=category,
                # 매직 바이트로 판별 — 확장자를 믿지 않는다.
                mime="image/jpeg" if blob[:3] == b"\xff\xd8\xff" else "image/png",
                data=blob,
                caption=caption,
                context_text=context or None,
                needs_vision=_needs_vision(category, context, caption),
            )
        )

    if figures:
        vision = sum(1 for f in figures if f.needs_vision)
        _log.info("그림 분리: %d개 (비전 필요 %d개)", len(figures), vision)
    return figures


def _needs_vision(category: str, context: str, caption: str | None) -> bool:
    """이미지를 실제로 봐야 하는가.

    차트는 무조건 대상이다 — 수치는 주변 문장에서 읽어낼 수 없다.

    나머지는 **주변 원문의 양**으로 판단한다. 캡션 유무를 필수 조건으로
    걸었더니 실측에서 21개 전부 true가 나왔다(이 교재는 "그림 1" 형식을
    아예 안 씀). 전부 true면 플래그가 아무것도 걸러주지 않는다.
    캡션은 원문이 애매할 때 판정을 눕히는 보조 신호로만 쓴다.
    """
    if category == "chart":
        return True
    if len(context) >= _VISION_MIN_CONTEXT_CHARS:
        return False
    # 원문이 짧아도 설명형 캡션이 있으면 그걸로 충분한 경우가 많다.
    return caption is None


def locate(
    figures: list[FigureDraft],
    segments: list[Segment],
    elements: list[Element],
) -> dict[int, tuple[int, int]]:
    """2-b단계 — 그림을 조각과 **본문 내 위치**에 매핑한다. Solar 0회.

    반환: {element_id: (조각 seq, 조각 content 안의 char offset)}

    조각 content는 요소 텍스트를 "\\n\\n"로 이어 붙인 것이므로, 조각에 실제로
    들어간 요소들의 길이를 순서대로 누적하면 그림이 원래 있던 지점이 나온다.
    데이터는 이미 다 있다 — 계산만 하면 된다.

    이게 없으면 그림이 전부 조각 맨 아래로 몰린다.
    """
    located: dict[int, tuple[int, int]] = {}
    by_element = {f.element_id for f in figures}

    for segment in segments:
        if segment.element_from is None or segment.element_to is None:
            continue

        offset = 0
        for index in range(segment.element_from, segment.element_to + 1):
            if not 0 <= index < len(elements):
                continue
            element = elements[index]
            # 조각화가 뺀 요소는 content에 없으므로 길이도 안 센다.
            # 판정은 segment 모듈 것을 그대로 쓴다 — 기준이 갈리면 offset이
            # 조용히 어긋난다.
            if not segment_module.is_included(element):
                continue

            if index in by_element:
                located[index] = (segment.seq, offset)
            # 그림 요소도 본문에 자기 자리를 차지한다 — Document Parse가
            # "![image](/image/placeholder)" 마크다운을 주고 그게 조각 content에
            # 그대로 들어간다. 여기서 길이를 안 더하면 같은 조각의 두 번째
            # 그림부터 30자씩 밀려 단어 중간을 가리킨다.
            offset += len(segment_module.element_text(element)) + 2  # "\n\n"

    _log.info("그림 위치 복원: %d/%d개", len(located), len(figures))
    return located
