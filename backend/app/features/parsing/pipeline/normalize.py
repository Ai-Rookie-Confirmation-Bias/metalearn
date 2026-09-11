"""2.5단계 — 제어문자 정규화. Solar 0회.

**보이지 않는 손상을 여기서 끊는다.**

실측(pilgi.pdf, 정처기 필기 핵심요약 45p): 어절 사이가 스페이스가 아니라
U+0007(BEL)이었다. 요소 2,017개 중 449개에 6,864개 — 전체 문자의 11%다.
BEL은 화면에도 마크다운에도 안 그려져서 눈으로는 "공백이 사라진 것"처럼
보이지만, 원인이 전혀 다르다. 그리고 정규식 \\s에 안 걸리기 때문에 뒷단계가
전부 오염된다:

  5단계   조각 경계·문자수 계산이 공백을 못 본다
  5-b     문장 분리 정규식(\\s+)이 어절 경계를 못 찾는다
  7단계   본문 단원 표기("1과목 소프트웨어 설계") 문자열 매칭이 실패한다
  8단계   LLM에 깨진 텍스트가 그대로 들어간다

위치는 **정제(3·4단계) 앞, 그림 분리(2단계) 뒤**다. 4단계가 LLM에 텍스트를
보내고 7단계가 문자열로 매칭하므로 그 전에 고쳐야 하고, base64를 이미
떼어낸 뒤라야 헛일이 없다.

이 단계는 두 가지를 한다 — **제어문자 치환**(normalize)과 **장식 제거**(clean).
둘 다 원문 층의 순수 로직이라 LLM을 부르지 않는다. 줄 병합은 오탐률을
못 재서 아직 안 한다.

실측 효과 (pilgi.pdf):
    제어문자   6,864개(11%) → 0
    공백 비율  14% → 25%
    avg_chars  30 → 30      ← 1:1 치환이라 정의상 안 변한다.
                              요소가 2,017개로 잘게 쪼개진 탓이지 BEL 탓이
                              아니다. 이 수치는 장식 제거·줄 병합이 올린다.
    길이       요소·필드 단위로 전부 보존 (검증 실패 시 예외)
"""
from __future__ import annotations

import collections
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from app.features.parsing.pipeline import quality
from app.features.parsing.schemas import Element

_log = logging.getLogger("uvicorn.error")

# 치환표. **1:1만 넣는다** — 길이가 바뀌면 5-b 문장 앵커의 char_start/end와
# 2-b 그림의 char_offset이 통째로 어긋난다. 그 둘은 조각 content 안의
# offset이라 원문 길이가 유일한 좌표계다.
#
# 실측 근거가 있는 문자만 넣는다. 지금은 U+0007 하나뿐이다 —
# 다른 제어문자는 이 자료에서 0건이라 넣을 이유가 없고, 근거 없이 넣으면
# 나중에 "왜 이게 여기 있나"를 아무도 답할 수 없게 된다.
_TARGETS: dict[str, str] = {
    "\x07": " ",  # BEL. pilgi.pdf에서 어절 사이 공백 자리에 6,864개
}

# 요소 본문이 들어 있는 필드. 실측상 BEL은 markdown에만 있었지만
# (text·html 0건) 파서 버전에 따라 갈릴 수 있어 셋 다 훑는다.
_TEXT_FIELDS = ("text", "markdown", "html")

# 프리뷰에 담을 변경 요소 표본 수와 길이. 앞뒤를 나란히 보여줘야 치환이
# 맞는지 눈으로 확인된다.
_SAMPLE_LIMIT = 5
_SAMPLE_CHARS = 240


@dataclass
class NormalizeReport:
    """치환 결과. 전후 품질을 **둘 다** 들고 있다.

    한쪽만 보면 "정상"이라는 사실이 무슨 의미인지 알 수 없다. 무엇이
    얼마나 있었고 지금 얼마인지를 같이 보여줘야 판단이 된다.
    """

    before: quality.ParseQuality
    after: quality.ParseQuality
    replaced: int = 0
    # {"U+0007": 6864}
    counts: dict[str, int] = field(default_factory=dict)
    changed_elements: list[int] = field(default_factory=list)
    samples: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        """치환 후 제어문자가 하나도 안 남았는가. 이 단계의 성공 조건."""
        return self.after.control_chars == 0


def normalize(elements: list[Element]) -> tuple[list[Element], NormalizeReport]:
    """제어문자를 치환한 **사본** 목록과 전후 품질 보고서를 돌려준다.

    원본을 그대로 두는 이유: 디버그 화면이 before/after를 나란히 그려야
    하고, in-place로 바꾸면 비교 대상이 사라진다.
    """
    before = quality.measure(elements)

    result: list[Element] = []
    counts: Counter[str] = Counter()
    changed: list[int] = []
    samples: list[dict[str, Any]] = []

    for index, element in enumerate(elements):
        copy = dict(element)
        content = dict(element.get("content") or {})
        hits = 0
        sample_before = sample_after = ""

        for name in _TEXT_FIELDS:
            value = content.get(name)
            if not isinstance(value, str):
                continue
            converted, found = _convert(value)
            if not found:
                continue
            _check_length(index, name, value, converted)
            content[name] = converted
            counts.update(found)
            hits += sum(found.values())
            if not sample_before:
                sample_before, sample_after = value, converted

        if hits:
            copy["content"] = content
            changed.append(index)
            if len(samples) < _SAMPLE_LIMIT:
                samples.append(
                    {
                        "idx": index,
                        "category": element.get("category"),
                        "page": element.get("page"),
                        "replaced": hits,
                        # before는 제어문자를 그대로 둔다 — 화면이 ␇ 배지로
                        # 그려야 "여기 있었다"가 보인다.
                        "before": sample_before[:_SAMPLE_CHARS],
                        "after": sample_after[:_SAMPLE_CHARS],
                    }
                )
        result.append(copy)

    after = quality.measure(result)
    report = NormalizeReport(
        before=before,
        after=after,
        replaced=sum(counts.values()),
        counts=dict(counts),
        changed_elements=changed,
        samples=samples,
    )

    _log.info(
        "제어문자 정규화: %d개 치환 %s — 요소 %d/%d 변경 · 제어문자 %d→%d · "
        "공백 %d%%→%d%%",
        report.replaced, report.counts, len(changed), len(elements),
        before.control_chars, after.control_chars,
        before.space_ratio, after.space_ratio,
    )
    if not report.is_clean:
        # 치환표에 없는 제어문자가 남은 것이다. 지우지 않고 알리기만 한다 —
        # 실측 근거 없이 치환표를 늘리지 않는다는 원칙이 우선이다.
        _log.warning(
            "정규화 후에도 제어문자 %d개 남음: %s — 치환표에 없는 문자다",
            after.control_chars, after.control_names,
        )
    return result, report


def _convert(value: str) -> tuple[str, dict[str, int]]:
    """치환된 문자열과 {유니코드 이름: 개수}. 없으면 원본 그대로 돌려준다."""
    found: dict[str, int] = {}
    converted = value
    for char, replacement in _TARGETS.items():
        count = converted.count(char)
        if count:
            found[f"U+{ord(char):04X}"] = count
            converted = converted.replace(char, replacement)
    return converted, found


# ─────────────────────────────────────────────────────────────────
# 장식 제거 — 반복 배지·러닝 타이틀·저작권 줄
# ─────────────────────────────────────────────────────────────────
#
# **category는 보지 않는다.** 3권 실측에서 같은 장식이 header/footer로 잡힌
# 비율이 ryan 100%(20/20) · network 68%(15/22) · pilgi 2%(1/45)로 요동쳤다.
# pilgi는 러닝 타이틀 45개가 paragraph 29 · heading1 15 · header 1로 갈렸고,
# network는 AWS 저작권 줄이 footer 15 · paragraph 7로 갈렸다. 게이트로 못 쓴다.
#
# 대신 **페이지 커버리지**로 가른다. 실측 분포:
#     장식  pilgi 초/치기·러닝 타이틀 100% · ryan Ⓒ 91% · network 저작권 63%
#     본문  network VPC 10.0.0.0/16 14% · Internet gateway 9% · pilgi 실행 2%
# 63%와 14% 사이가 비어 있어 0.4를 문턱으로 둔다. 표본 3권 기준이라
# 앞부분에만 있는 배너 같은 낮은 커버리지 장식을 만나면 다시 재야 한다.
COVERAGE_THRESHOLD = 0.4

# 보조 규칙 — 커버리지가 낮아도 좌표가 페이지 가장자리에 고정되고 페이지당
# 정확히 1회면 러닝 헤더다. ryan의 챕터 헤더("1. 소프트웨어 구축" 5회 = 23%)가
# 이 경로로 걸린다. 좌표는 Document Parse가 주는 0~1 정규화 폴리곤이다.
EDGE_TOP = 0.12
EDGE_BOTTOM = 0.88
EDGE_PIN_TOLERANCE = 0.02
RUNNING_HEAD_MIN_HITS = 3

# 부분 제거 상한. 줄에서 장식 문구를 뺀 나머지가 글자 없이 이 길이 이하일
# 때만 적용한다.
#
# 길이 조건이 없으면 목차 줄이 통과한다 — 실측: ryan의
# "- 1. 소프트웨어 구축 ……… 1"에서 러닝 헤더 문구를 빼면 "- ……… 1"이 남는데
# 점선과 숫자뿐이라 '글자 없음'을 통과해 **목차 항목이 지워졌다.** 7단계
# 목차 근거를 파괴하는 사고다. 8자면 "010"(3자)은 통과하고 목차 줄은 막힌다.
PARTIAL_MAX_CHARS = 8

_WS = re.compile(r"\s+")
_NUM = re.compile(r"\d+")
_LETTER = re.compile(r"[가-힣A-Za-z]")
# 이미지 마크다운이 든 요소는 통째로 지우지 않는다 — 그림이 본문에서 차지한
# 자리가 사라지면 2-b 그림 위치 복원이 끊긴다.
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MARKUP_EDGE = "#*_-–— \t"

_GROUP_SAMPLE_LIMIT = 12
_DIFF_SAMPLE_LIMIT = 5


@dataclass
class DecorationGroup:
    """장식으로 판정된 문구 묶음."""

    key: str
    reason: str          # repeat | running_head
    hits: int
    pages: int
    coverage: float
    phrases: list[str]   # 이 그룹에 속한 실제 원문 문구들


@dataclass
class CleanReport:
    elements_in: int = 0
    elements_out: int = 0
    # {사유: 요소 수}. marked만 센다 — 부분 제거는 요소가 남으므로 따로.
    removed: dict[str, int] = field(default_factory=dict)
    partial: int = 0
    chars_in: int = 0
    chars_out: int = 0
    # 의도한 제거량과 실제 제거량의 차이. **공백을 뺀 글자 수 기준**이다.
    # 줄을 지우면 줄바꿈이 함께 사라져 공백 회계가 어긋나는데, 그건 사고가
    # 아니라 잡음이다. 잡아야 할 것은 "지우기로 하지 않은 글자가 사라진 것"
    # 하나뿐이라 공백을 빼고 센다.
    unaccounted: int = 0
    groups: list[DecorationGroup] = field(default_factory=list)
    samples: list[dict[str, Any]] = field(default_factory=list)


def _flat(text: str) -> str:
    return _WS.sub(" ", text).strip()


def _group_key(text: str) -> str:
    """그룹핑 키 — 공백 압축 → 마크다운 장식 제거 → 숫자 마스킹.

    숫자를 지우는 이유: network의 저작권 줄이 연도·판본 차이로 22 + 6으로
    갈려 있었다. 마스킹하면 한 그룹(24)이 된다.
    """
    return _NUM.sub("#", _flat(text).strip(_MARKUP_EDGE).strip())


def _weight(text: str) -> int:
    """공백을 뺀 글자 수. 회계의 단위다."""
    return len(_WS.sub("", text))


def _band(element: Element) -> tuple[float, float] | None:
    ys = [p["y"] for p in element.get("coordinates") or [] if "y" in p]
    return (min(ys), max(ys)) if ys else None


def _classify(
    elements: list[Element], total_pages: int
) -> tuple[dict[str, DecorationGroup], set[str]]:
    """장식 그룹과 제거 대상 문구 집합을 찾는다."""
    buckets: dict[str, list[Element]] = collections.defaultdict(list)
    for element in elements:
        text = _element_text(element)
        if text:
            buckets[_group_key(text)].append(element)

    groups: dict[str, DecorationGroup] = {}
    for key, members in buckets.items():
        # 글자가 없는 키는 건드리지 않는다. 숫자 마스킹을 거치면 쪽번호와
        # 항목 번호가 전부 "#" 한 덩어리가 되는데, 실측(pilgi)에서 그 그룹이
        # 363개(항목 번호 293 · 쪽번호 45 · heading 25)였다. 커버리지 100%라
        # 그대로 두면 본문 번호 체계가 통째로 사라진다. 쪽번호는 뒤의 refine
        # 규칙이 잡는다.
        if len(members) < 2 or not _LETTER.search(key):
            continue

        pages = {m.get("page") for m in members}
        coverage = len(pages) / total_pages if total_pages else 0.0
        if coverage >= COVERAGE_THRESHOLD:
            reason = "repeat"
        elif _is_running_head(members, pages):
            reason = "running_head"
        else:
            continue

        groups[key] = DecorationGroup(
            key=key, reason=reason, hits=len(members), pages=len(pages),
            coverage=coverage,
            phrases=sorted({_flat(_element_text(m)) for m in members}),
        )

    phrases = {p for g in groups.values() for p in g.phrases if p}
    return groups, phrases


def _is_running_head(members: list[Element], pages: set[int | None]) -> bool:
    """커버리지가 낮아도 러닝 헤더인가 — 페이지당 1회 + 가장자리 고정."""
    if len(members) < RUNNING_HEAD_MIN_HITS or len(members) != len(pages):
        return False
    bands = [b for b in (_band(m) for m in members) if b is not None]
    if len(bands) != len(members):
        return False
    tops = [t for t, _ in bands]
    bottoms = [b for _, b in bands]
    at_edge = max(tops) < EDGE_TOP or min(bottoms) > EDGE_BOTTOM
    pinned = max(tops) - min(tops) < EDGE_PIN_TOLERANCE
    return at_edge and pinned


def clean(elements: list[Element]) -> tuple[list[Element], CleanReport]:
    """장식을 걷어낸 **사본**과 회계 보고서를 돌려준다.

    적용은 3단이고 위에서부터 먼저 걸리는 것을 쓴다:

      ① 요소 전체가 장식 그룹 → 요소를 removed 마킹 (물리 삭제 아님)
      ② 줄 전체가 장식 문구와 일치 → 그 줄만 제거
      ③ 줄에서 장식 문구를 뺀 나머지가 글자 없이 8자 이하 → 그 부분만 제거

    단순 부분 문자열 치환으로 하면 안 된다. 실측 사고: "초"가 헤더
    "초 시험에 나오는 것만 치기 공부한다!" 안에서도 매칭돼 "시험에 나오는
    것만 공부한다!" 잔해가 본문에 남았고, ryan에서는 목차 줄의 첫 항목이
    지워졌다. ①을 먼저 걸고 ②·③을 줄 단위로 제한해야 둘 다 막힌다.
    """
    report = CleanReport(elements_in=len(elements))
    if not elements:
        return list(elements), report

    total_pages = len({e.get("page") for e in elements if e.get("page") is not None})
    groups, phrases = _classify(elements, total_pages)
    report.groups = sorted(
        groups.values(), key=lambda g: -g.hits
    )[:_GROUP_SAMPLE_LIMIT]

    # 긴 문구부터 지워야 짧은 문구가 긴 문구를 갉아먹지 않는다.
    ordered = sorted(phrases, key=len, reverse=True)
    removed: Counter[str] = Counter()
    intended = actual = 0

    result: list[Element] = []
    for element in elements:
        text = _element_text(element)
        report.chars_in += len(text)
        if not text:
            result.append(dict(element))
            continue

        key = _group_key(text)
        if key in groups and not _IMAGE.search(text):
            copy = dict(element)
            copy["removed"] = groups[key].reason
            removed[groups[key].reason] += 1
            intended += _weight(text)
            actual += _weight(text)
            result.append(copy)
            continue

        new_text, line_intent = _strip_lines(text, phrases, ordered)
        if new_text == text:
            report.chars_out += len(text)
            result.append(dict(element))
            continue

        intended += line_intent
        actual += _weight(text) - _weight(new_text)

        if not new_text.strip():
            # 장식만 남아 있던 요소. 지우지 않고 마킹만 한다.
            copy = dict(element)
            copy["removed"] = "repeat"
            removed["repeat"] += 1
            result.append(copy)
            continue

        if len(report.samples) < _DIFF_SAMPLE_LIMIT:
            report.samples.append(
                {
                    "page": element.get("page"),
                    "category": element.get("category"),
                    "before": text[:_SAMPLE_CHARS],
                    "after": new_text[:_SAMPLE_CHARS],
                }
            )
        report.partial += 1
        report.chars_out += len(new_text)
        result.append(_replace_text(element, new_text))

    report.removed = dict(removed)
    report.elements_out = len(elements) - sum(removed.values())
    report.unaccounted = actual - intended

    if report.unaccounted:
        # 지우기로 하지 않은 글자가 사라졌다. 항등식이 아니라 의도와의
        # 대조라서, 여기가 울리면 규칙이 원문을 갉아먹고 있다는 뜻이다.
        raise ValueError(
            f"장식 제거 회계 불일치: 실제 {actual}자 · 의도 {intended}자 "
            f"(차이 {report.unaccounted}). 의도하지 않은 원문이 사라졌습니다."
        )

    _log.info(
        "장식 제거: %d종 → 요소 %d개 마킹 %s · 부분 제거 %d개 "
        "(요소 %d→%d · %d→%d자)",
        len(groups), sum(removed.values()), dict(removed), report.partial,
        report.elements_in, report.elements_out,
        report.chars_in, report.chars_out,
    )
    for group in report.groups[:6]:
        _log.info(
            "  [%s] %d회 · 커버리지 %.0f%% · %r",
            group.reason, group.hits, group.coverage * 100, group.key[:40],
        )
    return result, report


def _strip_lines(
    text: str, phrases: set[str], ordered: list[str]
) -> tuple[str, int]:
    """②·③을 줄 단위로 적용한다. 반환: (새 텍스트, 의도한 제거량).

    의도량은 **실제로 매칭된 장식 문구의 길이를 따로 세어** 만든다. 결과
    텍스트와의 차이로 역산하면 항등식이 되어 아무것도 검증하지 못한다.
    이렇게 세면 치환이 연쇄되거나 인접 문자를 함께 먹는 순간 회계가 어긋난다.
    """
    kept: list[str] = []
    intended = 0

    for line in text.splitlines():
        flat = _flat(line)
        if not flat:
            kept.append(line)
            continue

        if flat in phrases:  # ② 줄 전체가 장식
            intended += _weight(flat)
            continue

        rest = flat
        matched = 0
        for phrase in ordered:
            if not phrase or phrase not in rest:
                continue
            matched += rest.count(phrase) * _weight(phrase)
            rest = rest.replace(phrase, " ")
        rest = _flat(rest)

        # ③ 남은 게 글자 없이 짧을 때만. 목차 줄(점선+쪽번호)이 여기서 걸러진다.
        if matched and not _LETTER.search(rest) and len(rest) <= PARTIAL_MAX_CHARS:
            intended += matched
            if rest:
                kept.append(rest)
            continue

        kept.append(line)

    return "\n".join(kept).strip(), intended


def _replace_text(element: Element, new_text: str) -> Element:
    """element_text()가 읽는 필드만 바꾼다.

    markdown이 있으면 그쪽이 파이프라인의 입력이므로 text·html은 손대지
    않는다. 여러 필드를 동시에 고치면 어느 쪽이 정본인지 흐려지고 회계도
    두 번 세게 된다.
    """
    copy = dict(element)
    content = dict(element.get("content") or {})
    field_name = "markdown" if content.get("markdown") else "text"
    content[field_name] = new_text
    copy["content"] = content
    return copy


def _element_text(element: Element) -> str:
    content = element.get("content") or {}
    return str(content.get("markdown") or content.get("text") or "").strip()


def _check_length(index: int, name: str, before: str, after: str) -> None:
    """길이 보존 검증.

    assert를 쓰지 않는다 — 파이썬 -O에서 통째로 사라지므로 운영에서
    보증이 없어진다. 여기가 깨지면 뒷단계 offset이 전부 어긋나므로
    조용히 넘어가는 것보다 파싱을 세우는 편이 낫다.
    """
    if len(before) == len(after):
        return
    raise ValueError(
        f"정규화가 길이를 바꿨습니다 (요소 #{index}.{name}): "
        f"{len(before)} → {len(after)}. 치환표에 1:1이 아닌 항목이 있습니다."
    )
