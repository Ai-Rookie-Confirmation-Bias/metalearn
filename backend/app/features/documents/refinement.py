"""문서 정제 v1 (ISSUE-014): 파서 elements → 운영용 원본.

원칙:
- 물리 삭제 금지: 제거 대상은 removed=<사유> 마킹만. 오판 시 마크만 떼면
  복구되므로, 파서 오분류(본문을 header로 등)에도 데이터 손실이 없다.
- LLM은 위치 판정만: 본문 시작점·파트 경계·프로파일을 요소 번호/라벨로만
  받는다. 본문 텍스트를 재생성하지 않으므로 환각이 원본에 유입될 수 없다.
- 애매하면 남긴다: 규칙은 기계가 확신할 수 있는 것만, 스캔 판정은
  가드레일(수상하면 기각)로 방어. 잘못 남김=소음, 잘못 지움=손실이라
  피해가 비대칭이기 때문.

산출물(문서당): {"scan": <LLM 판정 감사 기록>, "elements": [...]}
- elements 각 원소에 removed(제거 사유)·part(파트 번호) 키가 추가된다.
- profile(linked|enumerative|mixed)은 v1에서 저장만 하고 활용하지 않는다.
"""
import json
import logging
import re
from collections import Counter
from typing import Any

from app.core.llm.solar import solar_client
from app.features.documents.sectioning import _element_text

_log = logging.getLogger("uvicorn.error")

PROFILES = {"linked", "enumerative", "mixed"}

# ── 1층: 규칙 정제 ──────────────────────────────────────────────────
_DECORATION_CATEGORIES = {"header", "footer", "footnote"}
# 장식 판정 교차검증: 파서 라벨만 믿지 않고 "여러 위치에서 반복" 또는
# "아주 짧음(페이지 번호류)"일 때만 제거. 길고 유일한 텍스트는 파서
# 오분류(본문일 가능성)로 보고 남긴다.
_DECORATION_MAX_UNIQUE_CHARS = 20

# 목차 줄: "- 1. 소프트웨어 구축 ……… 1" — 점선 리더 + 페이지 번호.
_TOC_LINE_RE = re.compile(r"^\s*[-*•]?\s*\d+\.\s*.+?[….·⋯]{2,}\s*\d+\s*$")

_COPYRIGHT_KEYWORDS = ("저작권", "무단", "복제", "배포", "2차적 저작물", "벌금", "민사상")

# ── 2층: LLM 문서 스캔 ──────────────────────────────────────────────
_SCAN_HEAD_ELEMENTS = 40      # 앞부분 원문을 통째로 보여줄 요소 수
_SCAN_HEAD_TEXT_CHARS = 200   # 앞부분 요소당 원문 절단 길이
# 가드레일: 본문 시작점이 문서 앞 이 비율(또는 head 범위)을 넘으면
# 판정을 기각하고 아무것도 지우지 않는다.
_FRONT_MATTER_MAX_RATIO = 0.25

_SCAN_SYSTEM = (
    "너는 학습 자료 문서의 구조를 판정하는 분석기다. "
    "출력은 반드시 지정한 JSON 스키마만 따른다. "
    "본문 내용을 생성하거나 고쳐 쓰지 말고, 요소 번호와 라벨로만 답한다."
)


def apply_rules(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """1층 규칙 정제: 확실한 노이즈만 removed 마킹한 사본 목록을 반환."""
    decoration_freq: Counter[str] = Counter(
        _element_text(el)
        for el in elements
        if el.get("category") in _DECORATION_CATEGORIES
    )

    refined: list[dict[str, Any]] = []
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
    return refined


def _is_toc(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    matched = sum(1 for line in lines if _TOC_LINE_RE.match(line))
    return matched >= len(lines) / 2


def _is_copyright(text: str) -> bool:
    return sum(1 for kw in _COPYRIGHT_KEYWORDS if kw in text) >= 3


def _scan_prompt(elements: list[dict[str, Any]]) -> str:
    headings = [
        f"{i}: {_element_text(el)[:80]}"
        for i, el in enumerate(elements)
        if el.get("category") in ("heading1", "heading2", "heading3")
    ]
    head = [
        f"{i} [{el.get('category')}]: {_element_text(el)[:_SCAN_HEAD_TEXT_CHARS]}"
        for i, el in enumerate(elements[:_SCAN_HEAD_ELEMENTS])
        if not el.get("removed")
    ]
    return (
        "학습 자료 문서를 파서가 요소 배열로 분해했다. 아래는 문서의 "
        "헤딩(제목) 목록 전체와, 앞부분 요소들의 원문이다.\n"
        "다음 세 가지를 판정하라:\n"
        "1. body_start_element: 실제 학습 본문이 시작되는 요소 번호. "
        "표지·인사말·목차·저작권 고지·구매 안내 등 비학습 콘텐츠가 끝난 "
        "직후의 요소다. 문서가 처음부터 본문이면 0.\n"
        "2. profile: 문서의 지배적 성격. "
        '"linked"=개념이 선수 사슬로 쌓이는 문서(수학·물리 교재처럼 앞 개념 '
        '없이 뒤 개념 이해 불가), "enumerative"=병렬 나열·암기형(자격증 '
        '요약노트·용어집처럼 항목 간 의존이 약함), "mixed"=두 성격이 비등.\n'
        "3. parts: 최상위 주제 단위(목차의 장/파트)가 시작되는 헤딩 요소 "
        "번호 목록. 목차가 있으면 목차 항목과 헤딩을 대조해 찾아라. "
        "명확한 파트 구분이 없으면 빈 배열.\n\n"
        'JSON 형식: {"body_start_element": int, '
        '"profile": "linked|enumerative|mixed", '
        '"parts": [{"title": str, "start_element": int}]}\n\n'
        "=== 헤딩 목록 ===\n" + "\n".join(headings) +
        "\n\n=== 앞부분 요소 원문 ===\n" + "\n".join(head)
    )


def _sanitize_scan(raw: dict[str, Any], total: int) -> dict[str, Any]:
    """LLM 판정에 가드레일 적용. 수상한 판정은 기각(=아무것도 안 지움)."""
    scan: dict[str, Any] = {"body_start_element": 0, "profile": None, "parts": []}

    body_start = raw.get("body_start_element")
    limit = max(_SCAN_HEAD_ELEMENTS, int(total * _FRONT_MATTER_MAX_RATIO))
    if isinstance(body_start, int) and 0 <= body_start <= limit:
        scan["body_start_element"] = body_start
    elif body_start:
        _log.warning("스캔 기각: body_start_element=%s (한계 %d)", body_start, limit)

    profile = raw.get("profile")
    if profile in PROFILES:
        scan["profile"] = profile

    prev = -1
    for part in raw.get("parts") or []:
        start = part.get("start_element") if isinstance(part, dict) else None
        if isinstance(start, int) and prev < start < total:
            scan["parts"].append(
                {"title": str(part.get("title", ""))[:80], "start_element": start}
            )
            prev = start
    return scan


def apply_scan(elements: list[dict[str, Any]], scan: dict[str, Any]) -> None:
    """스캔 판정을 마킹으로 반영: 서문 removed + 파트 번호 부여 (in-place)."""
    body_start = scan["body_start_element"]
    boundaries = [p["start_element"] for p in scan["parts"]]
    part = 0
    for i, el in enumerate(elements):
        if i < body_start and not el.get("removed"):
            el["removed"] = "front_matter"
        while part < len(boundaries) and i >= boundaries[part]:
            part += 1
        el["part"] = part


async def refine(
    elements: list[dict[str, Any]],
) -> tuple[dict[str, Any], str | None]:
    """정제 전체 수행. 반환: ({"scan":…, "elements":…}, profile).

    스캔 LLM이 실패해도 규칙 정제만으로 진행한다 — 정제는 ingest를
    죽일 만큼 중요하지 않다.
    """
    refined = apply_rules(elements)
    scan: dict[str, Any] | None = None
    if refined:
        try:
            raw = await solar_client.generate_json(
                _scan_prompt(refined), system=_SCAN_SYSTEM
            )
            scan = _sanitize_scan(raw, total=len(refined))
        except Exception as exc:  # noqa: BLE001 — 스캔 실패는 비치명
            _log.warning("문서 스캔 실패, 규칙 정제만 적용: %s", exc)
    if scan is not None:
        apply_scan(refined, scan)
    removed = Counter(el["removed"] for el in refined if el.get("removed"))
    _log.info(
        "정제 완료: %d요소 중 제거 마킹 %d개 %s, 파트 %d개, 프로파일 %s",
        len(refined),
        sum(removed.values()),
        dict(removed),
        len(scan["parts"]) if scan else 0,
        scan["profile"] if scan else None,
    )
    return {"scan": scan, "elements": refined}, (scan or {}).get("profile")
