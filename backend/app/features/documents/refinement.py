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
    # 객관 통계 주입: 판정을 인상이 아니라 수치에 접지시켜 실행 간 편차를
    # 줄인다 (실측: 같은 문서에서 프로파일 linked↔enumerative 널뛰기).
    stats = Counter(str(el.get("category")) for el in elements)
    return (
        "학습 자료 문서를 파서가 요소 배열로 분해했다. 아래는 문서 통계, "
        "헤딩(제목) 목록 전체, 앞부분 요소들의 원문이다.\n"
        f"문서 통계: 총 {len(elements)}요소 — "
        f"수식 {stats.get('equation', 0)}, 표 {stats.get('table', 0)}, "
        f"문단 {stats.get('paragraph', 0)}, 헤딩 "
        f"{stats.get('heading1', 0) + stats.get('heading2', 0) + stats.get('heading3', 0)}\n\n"
        "다음 세 가지를 판정하라:\n"
        "1. body_start_element: 실제 학습 본문이 시작되는 요소 번호.\n"
        "   - 비학습 콘텐츠는 오직: 표지, 저자 인사말, 목차, 저작권 고지, 구매 안내.\n"
        "   - 주의: '준비 학습', '생각 열기', 연습 문제, 수식·표·그래프가 있는 "
        "요소는 학습 본문이다 — 절대 비학습으로 분류하지 말 것.\n"
        "   - 애매하면 본문 시작을 앞당겨라(덜 지우는 쪽이 안전). "
        "문서가 처음부터 본문이면 0.\n"
        "2. profile: 문서의 지배적 성격. 통계를 근거로 판정하라.\n"
        '   - "linked": 개념이 선수 사슬로 쌓임 — 수식 비중이 높고 예제·증명이 '
        "순차 전개되는 수학·과학 교재 유형.\n"
        '   - "enumerative": 병렬 나열·암기형 — 짧은 정의·표가 많고 헤딩이 '
        "수십 개 이상 반복되는 요약노트·용어집 유형.\n"
        '   - "mixed": 두 성격이 실제로 비등할 때만. 확신이 서면 mixed를 피할 것.\n'
        "3. parts: 최상위 주제 단위(목차의 장/파트)가 시작되는 헤딩 요소 번호 목록.\n"
        "   - 목차가 있으면 반드시 목차 항목과 헤딩을 대조해서 찾아라 "
        "(목차 항목 수 = parts 수가 되는 것이 정상).\n"
        "   - 소제목·절 단위는 파트가 아니다. 단일 장 문서면 빈 배열.\n"
        '   - 각 파트에 kind를 부여하라: "unit" = 정규 학습 단원(목차의 장), '
        '"special" = 특집·부록·진로/직업 소개·읽을거리 코너처럼 본 과목의 '
        "학습 주제가 아닌 파트(예: 수학 교재 속 'IoT는 무엇인가요?' 코너). "
        "애매하면 unit(덜 배제하는 쪽이 안전).\n\n"
        'JSON 형식: {"body_start_element": int, '
        '"profile": "linked|enumerative|mixed", '
        '"parts": [{"title": str, "start_element": int, "kind": "unit|special"}]}\n\n'
        "=== 헤딩 목록 ===\n" + "\n".join(headings) +
        "\n\n=== 앞부분 요소 원문 ===\n" + "\n".join(head)
    )


# front matter 제거 구간에 이 카테고리가 있으면 판정 기각 — 표지/인사말에는
# 수식·표가 없다. 실측 사고: 미적분 '준비 학습'(표 2개 포함)이 서문으로
# 오판돼 교재 개념 80→49 급감 (removed 마킹 덕에 무손실 복구).
_BODY_EVIDENCE_CATEGORIES = {"table", "equation", "chart"}

# 파트(장) 개수 상식 상한 — 초과하면 소제목을 파트로 오인한 것 (실측: 단일
# 단원 미적분에서 57개). 틀린 경계로 청크를 잘게 쪼개느니 경계 없이 간다.
_MAX_PARTS = 20


def _sanitize_scan(
    raw: dict[str, Any], elements: list[dict[str, Any]]
) -> dict[str, Any]:
    """LLM 판정에 가드레일 적용. 수상한 판정은 기각(=아무것도 안 지움)."""
    total = len(elements)
    scan: dict[str, Any] = {"body_start_element": 0, "profile": None, "parts": []}

    body_start = raw.get("body_start_element")
    limit = max(_SCAN_HEAD_ELEMENTS, int(total * _FRONT_MATTER_MAX_RATIO))
    if isinstance(body_start, int) and 0 <= body_start <= limit:
        evidence = [
            el.get("category")
            for el in elements[:body_start]
            if el.get("category") in _BODY_EVIDENCE_CATEGORIES
        ]
        if evidence:
            _log.warning(
                "스캔 기각: 서문 구간(~%d)에 본문 증거 요소 %s — 지우지 않음",
                body_start, evidence,
            )
        else:
            scan["body_start_element"] = body_start
    elif body_start:
        _log.warning("스캔 기각: body_start_element=%s (한계 %d)", body_start, limit)

    profile = raw.get("profile")
    if profile in PROFILES:
        scan["profile"] = profile

    raw_parts = raw.get("parts") or []
    if len(raw_parts) > _MAX_PARTS:
        _log.warning("스캔 기각: parts %d개 (상한 %d) — 파트 경계 미적용", len(raw_parts), _MAX_PARTS)
        raw_parts = []
    prev = -1
    for part in raw_parts:
        start = part.get("start_element") if isinstance(part, dict) else None
        if isinstance(start, int) and prev < start < total:
            kind = part.get("kind") if isinstance(part, dict) else None
            scan["parts"].append(
                {
                    "title": str(part.get("title", ""))[:80],
                    "start_element": start,
                    # 파트 성격 (ISSUE-018): unit=정규 단원, special=특집/부록 코너.
                    # 배치고사 천장·문항 선정에서 special 제외용. 기본 unit.
                    "kind": kind if kind in ("unit", "special") else "unit",
                }
            )
            prev = start
    # 가드레일: special이 절반을 넘으면 라벨 전체 기각(전부 unit) — 과도 판정
    # 시 배치고사가 물을 파트가 사라지는 사고 방지.
    specials = sum(1 for p in scan["parts"] if p["kind"] == "special")
    if scan["parts"] and specials / len(scan["parts"]) > 0.5:
        _log.warning("스캔 기각: special 파트 %d/%d — 라벨 무시", specials, len(scan["parts"]))
        for p in scan["parts"]:
            p["kind"] = "unit"
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
            scan = _sanitize_scan(raw, refined)
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
