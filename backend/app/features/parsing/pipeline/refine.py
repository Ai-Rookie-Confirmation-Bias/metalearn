"""3·4단계 — 정제. 규칙(호출 0회) + LLM 스캔(호출 1회).

원칙: **물리 삭제 금지.** 제거 대상은 removed=<사유> 마킹만 한다.
오판해도 마크만 떼면 복구된다. 잘못 남기면 소음이지만 잘못 지우면 손실이라
피해가 비대칭이기 때문이다.

3단계(규칙)는 기계가 확신할 수 있는 것만 본다 — 반복되는 머리말·꼬리말,
점선 리더가 있는 목차 페이지, 저작권 키워드 뭉치.

4단계(LLM)는 규칙으로 못 잡는 표지·인사말·구매 안내를 걷어낸다. 판정 하나만
묻고 가드레일 두 개로 방어한다. 파트 경계 판정은 7단계가 대체하므로 없다.
"""
from __future__ import annotations

import logging
import re
from collections import Counter

from app.core.llm.solar import solar_client
from app.features.parsing.prompts import refine_scan
from app.features.parsing.schemas import Element

_log = logging.getLogger("uvicorn.error")

_DECORATION_CATEGORIES = {"header", "footer", "footnote"}
# 장식 판정 교차검증: 파서 라벨만 믿지 않는다. "여러 위치에서 반복" 또는
# "아주 짧음(페이지 번호류)"일 때만 제거한다. 길고 유일한 텍스트는 파서
# 오분류(본문일 가능성)로 보고 남긴다 — 실측에서 챕터 제목이 header로
# 분류되는 일이 실제로 있었다.
_DECORATION_MAX_UNIQUE_CHARS = 20

# 목차 줄: "- 1. 소프트웨어 구축 ……… 15" — 점선 리더 + 페이지 번호.
_TOC_LINE_RE = re.compile(r"^\s*[-*•]?\s*\d+\.\s*.+?[….·⋯]{2,}\s*\d+\s*$")

# 3개 이상 동시 출현해야 저작권 고지로 본다. 본문에서 "복제"나 "배포"
# 한 단어가 나오는 건 흔하다.
_COPYRIGHT_KEYWORDS = ("저작권", "무단", "복제", "배포", "2차적 저작물", "벌금", "민사상")


def _element_text(element: Element) -> str:
    content = element.get("content") or {}
    return str(content.get("markdown") or content.get("text") or "").strip()


def apply_rules(elements: list[Element]) -> list[Element]:
    """확실한 노이즈만 removed 마킹한 **사본** 목록을 반환한다."""
    decoration_freq: Counter[str] = Counter(
        _element_text(el)
        for el in elements
        if el.get("category") in _DECORATION_CATEGORIES
    )

    refined: list[Element] = []
    for el in elements:
        copy = dict(el)
        text = _element_text(el)
        if el.get("category") in _DECORATION_CATEGORIES and (
            decoration_freq[text] >= 2 or len(text) <= _DECORATION_MAX_UNIQUE_CHARS
        ):
            copy["removed"] = "decoration"
        elif _is_toc(text):
            copy["removed"] = "toc"
        elif _is_copyright(text):
            copy["removed"] = "copyright"
        refined.append(copy)

    removed = Counter(el["removed"] for el in refined if el.get("removed"))
    _log.info(
        "규칙 정제: %d요소 중 제거 마킹 %d개 %s",
        len(refined), sum(removed.values()), dict(removed),
    )
    return refined


def _is_toc(text: str) -> bool:
    """목차 페이지 판정 — 점선 리더 줄이 과반이면 목차다."""
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    matched = sum(1 for line in lines if _TOC_LINE_RE.match(line))
    return matched >= len(lines) / 2


# "- 1. 소프트웨어 구축 ……… 1" → ("소프트웨어 구축", 1)
_TOC_ENTRY_RE = re.compile(
    r"^\s*[-*•]?\s*(\d+)\.\s*(.+?)\s*[….·⋯]{2,}\s*(\d+)\s*$"
)


def extract_toc(elements: list[Element]) -> list[dict[str, object]]:
    """목차 페이지에서 항목과 시작 페이지를 뽑는다. Solar 0회.

    **자료에 목차가 있으면 그게 정답이다.** 저자가 직접 나눈 단원 구분이라
    LLM이 지어내는 것보다 항상 낫고, 페이지 번호까지 있으면 조각 배정을
    계산만으로 끝낼 수 있다.

    본문에서는 여전히 removed로 빼둔다(목차 줄 자체는 학습 내용이 아니다).
    빼는 것과 버리는 것은 다르다 — 기존 구현은 버려서 이 정보를 못 썼다.
    """
    entries: list[dict[str, object]] = []
    for el in elements:
        if el.get("removed") != "toc":
            continue
        for line in _element_text(el).splitlines():
            match = _TOC_ENTRY_RE.match(line)
            if match is None:
                continue
            entries.append(
                {
                    "no": int(match.group(1)),
                    "title": match.group(2).strip()[:200],
                    "page": int(match.group(3)),
                }
            )

    # 번호와 페이지가 함께 증가해야 진짜 목차다. 어긋나면 신뢰하지 않는다.
    ordered = [
        e for i, e in enumerate(entries)
        if i == 0 or (e["no"] > entries[i - 1]["no"] and e["page"] >= entries[i - 1]["page"])
    ]
    if len(ordered) < 2:
        return []

    _log.info(
        "목차 추출: %d개 항목 — %s",
        len(ordered), [f"{e['title']}(p.{e['page']})" for e in ordered],
    )
    return ordered


# "1. 소프트웨어 구축" — 러닝 헤더의 단원 표기.
_SECTION_HEADER_RE = re.compile(r"^\s*(\d{1,2})[.)]\s*(\S.{0,38})\s*$")


def extract_page_sections(elements: list[Element]) -> dict[int, str]:
    """페이지별 러닝 헤더에서 그 페이지가 속한 단원을 읽는다. Solar 0회.

    **이게 목차 배정의 가장 정확한 근거다.** 페이지마다 단원명이 직접 찍혀
    있으므로 추론도, 페이지 번호 보정도 필요 없다.

    목차 페이지의 인쇄 페이지 번호는 PDF 페이지와 어긋난다(실측: 정확히 3 차이).
    러닝 헤더는 그 문제 자체가 없다.

    반환: {PDF 페이지: 단원명}. 단원 번호가 페이지 순으로 단조 증가하지
    않으면 러닝 헤더가 아니라고 보고 빈 dict를 돌려준다.
    """
    per_page: dict[int, tuple[int, str]] = {}
    for el in elements:
        if el.get("category") not in _DECORATION_CATEGORIES:
            continue
        page = el.get("page")
        if page is None:
            continue
        match = _SECTION_HEADER_RE.match(_element_text(el))
        if match is None:
            continue
        entry = (int(match.group(1)), match.group(2).strip())
        # 한 페이지에 여러 개면 번호가 작은 쪽(상위 단원)을 쓴다.
        if page not in per_page or entry < per_page[page]:
            per_page[page] = entry

    if len(per_page) < 2:
        return {}

    numbers = [per_page[p][0] for p in sorted(per_page)]
    if any(b < a for a, b in zip(numbers, numbers[1:])):
        _log.warning("러닝 헤더 무시: 단원 번호가 페이지 순으로 증가하지 않음")
        return {}
    if len(set(numbers)) < 2:
        return {}

    sections = {page: f"{no}. {title}" for page, (no, title) in per_page.items()}
    _log.info(
        "러닝 헤더에서 단원 확인: %d페이지 → 단원 %d개",
        len(sections), len(set(numbers)),
    )
    return sections


# "1과목 소프트웨어 설계" · "제3장 정규화" · "Chapter 2. Memory" · "PART 4 …"
_BODY_SECTION_RE = re.compile(
    r"^\s*(?:제\s*)?(\d{1,2})\s*(?:과목|단원|장|편|부)\s*[.:]?\s*(.{0,40})$"
    r"|^\s*(?:Chapter|CHAPTER|Part|PART)\s*(\d{1,2})\s*[.:]?\s*(.{0,40})$"
)
# 표기 뒤에 붙는 제목의 최대 길이 — 이보다 길면 본문이지 제목이 아니다.
_BODY_TITLE_MAX = 40


def _clean_marker(text: str) -> str:
    """마크다운 장식과 공백을 걷어낸 한 줄로 만든다.

    Document Parse가 단원 표기를 heading으로 분류하면 "# 2과목"처럼 나온다.
    실측: 5개 표기 중 하나만 heading이라 그것만 검출에서 빠졌다.
    """
    return " ".join(text.split()).lstrip("#*_ ").strip()


def extract_body_sections(elements: list[Element]) -> list[dict[str, object]]:
    """본문 안의 단원 표기를 찾는다. Solar 0회.

    러닝 헤더가 없어도 단원 경계가 본문에 찍혀 있는 자료가 많다.
    실측(정처기 필기 요약): 본문에 "1과목 소프트웨어 설계" … "5과목 정보시스템
    구축 관리"가 그대로 있었는데, 이걸 안 보고 LLM에게 목차를 지어내게 했더니
    "재사용 및 버전 관리" 같은 엉뚱한 단원이 나왔다.

    Document Parse가 표기와 제목을 다른 요소로 쪼개는 일이 있어
    ("2과목" / "소프트웨어 개발") 뒤 요소에서 제목을 이어붙인다.

    반환: [{"index": 요소번호, "no": 단원번호, "title": 제목}]
    번호가 순서대로 증가하지 않으면 본문 속 우연한 문구로 보고 버린다.
    """
    found: list[dict[str, object]] = []
    for i, el in enumerate(elements):
        text = _clean_marker(_element_text(el))
        if not text or len(text) > 60:
            continue
        match = _BODY_SECTION_RE.match(text)
        if match is None:
            continue

        no = int(match.group(1) or match.group(3))
        title = (match.group(2) or match.group(4) or "").strip(" .:-")

        # 표기만 있고 제목이 없으면 뒤 요소에서 가져온다.
        # 실측: Document Parse가 "# 2과목" / "소프트웨어 개발"로 쪼갰다.
        if not title:
            for j in range(i + 1, min(i + 3, len(elements))):
                nearby = _clean_marker(_element_text(elements[j]))
                if nearby and len(nearby) <= _BODY_TITLE_MAX:
                    title = nearby
                    break
        if not title:
            continue

        found.append({"index": i, "no": no, "title": title[:100]})

    # 번호가 순서대로 증가해야 진짜 단원 표기다.
    ordered: list[dict[str, object]] = []
    for entry in found:
        if not ordered or int(entry["no"]) > int(ordered[-1]["no"]):
            ordered.append(entry)
    if len(ordered) < 2:
        return []

    _log.info(
        "본문 단원 표기 %d개: %s",
        len(ordered), [f"{e['no']}. {e['title']}" for e in ordered],
    )
    return ordered


def _is_copyright(text: str) -> bool:
    return sum(1 for kw in _COPYRIGHT_KEYWORDS if kw in text) >= 3


# ── 4단계: LLM 스캔 ────────────────────────────────────────────────

# 가드레일 ①: 본문 시작점이 문서 앞 이 비율을 넘으면 기각.
_FRONT_MATTER_MAX_RATIO = 0.25
# 가드레일 ②: 제거 구간에 이 카테고리가 있으면 기각 — 표지·인사말에
# 표나 수식이 있을 리 없다. 있다면 본문을 지우려는 것이다.
#
# 실측 사고 기록: 미적분 교재의 '준비 학습'(표 2개 포함)이 서문으로 오판돼
# 개념이 80개에서 49개로 급감했다. removed 마킹이라 무손실 복구는 됐지만,
# 이 가드레일이 있었으면 애초에 안 일어났을 일이다.
_BODY_EVIDENCE_CATEGORIES = {"table", "equation", "chart"}


async def apply_scan(elements: list[Element]) -> int:
    """본문 시작 지점 앞을 front_matter로 마킹한다 (in-place). 반환: 마킹 수.

    실패하거나 판정이 수상하면 **아무것도 지우지 않는다.** 정제는 파이프라인을
    죽일 만큼 중요하지 않고, 덜 지우는 쪽이 언제나 안전하다.
    """
    if not elements:
        return 0

    try:
        raw = await solar_client.generate_json(
            refine_scan.build_prompt(elements, _element_text),
            system=refine_scan.SYSTEM,
        )
    except Exception as exc:  # noqa: BLE001 — 스캔 실패는 비치명
        _log.warning("정제 스캔 실패, 규칙 정제만 적용: %s", exc)
        return 0

    body_start = _sanitize_body_start(raw.get("body_start_element"), elements)
    if body_start <= 0:
        return 0

    marked = 0
    for el in elements[:body_start]:
        if not el.get("removed"):
            el["removed"] = "front_matter"
            marked += 1

    _log.info("정제 스캔: 요소 0~%d를 서문으로 마킹 (%d개)", body_start - 1, marked)
    return marked


def _sanitize_body_start(value: object, elements: list[Element]) -> int:
    """가드레일 2개. 통과 못 하면 0(=아무것도 안 지움)."""
    total = len(elements)
    limit = max(refine_scan.HEAD_ELEMENTS, int(total * _FRONT_MATTER_MAX_RATIO))

    if not isinstance(value, int) or isinstance(value, bool):
        return 0
    if not 0 <= value <= limit:
        if value:
            _log.warning("정제 스캔 기각: body_start=%s (한계 %d)", value, limit)
        return 0

    evidence = [
        el.get("category")
        for el in elements[:value]
        if el.get("category") in _BODY_EVIDENCE_CATEGORIES
    ]
    if evidence:
        _log.warning(
            "정제 스캔 기각: 서문 구간(~%d)에 본문 증거 요소 %s — 지우지 않음",
            value, evidence,
        )
        return 0

    return value
