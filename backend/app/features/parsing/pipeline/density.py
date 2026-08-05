"""12단계 — 밀도·커버리지 측정. Solar 0회.

기획의 핵심 주장이 이 판정에 걸려 있다:

    내 자료가 범위를 정하고, 공용 교과서가 내용을 채운다.

"채워야 하는지"를 알려면 **내 자료가 내용까지 촘촘한지**를 재야 한다.
PPT 슬라이드는 뼈대는 되지만 본문은 못 된다. 교재는 둘 다 된다.
그 경계를 여기서 수치로 가른다.

⚠️ 기준값은 실측으로 정한다. 지금 값은 아래 근거로 잡았고, 형식별 표본이
   쌓이면 다시 조정해야 한다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.features.parsing.models import DensityGrade
from app.features.parsing.schemas import Segment

_log = logging.getLogger("uvicorn.error")

# 페이지당 본문 글자수 하한. 이 아래면 설명이 아니라 항목 나열로 본다.
#
# **조각당 평균을 쓰면 안 된다.** 조각은 문자 예산(4,000자)까지 채워서 끊으므로
# 자료가 얇으면 조각 *개수*만 줄고 평균은 예산 근처로 수렴한다. 즉 조각당
# 평균은 자료의 밀도가 아니라 조각화 설정을 재는 값이다.
#
# 실측 3권 (2026-08-05):
#                          조각당 평균    페이지당      실제 성격
#   network (슬라이드)        3,212자        299자      뼈대 — 표제어 나열
#   pilgi   (필기 요약집)     3,351자      1,266자      본문 가능
#   ryan    (실기 요약노트)   3,557자      3,396자      본문 가능
#
# 조각당 평균은 셋이 3,200~3,600으로 붙어 있어 아무것도 못 가른다(실제로 3권
# 모두 '본문 가능'으로 나왔다). 페이지당은 299 대 1,266으로 4배 넘게 갈린다.
# 뼈대 최댓값 299와 본문 최솟값 1,266 사이를 잡아 800으로 둔다.
BODY_MIN_CHARS_PER_PAGE = 800

# 개념이 붙은 조각 비율 하한(%). 조각은 있는데 개념이 안 나온다면 그 원문은
# 설명이 아니라 목록·표지·연습문제일 가능성이 높다.
BODY_MIN_COVERAGE = 60


@dataclass
class DensityReport:
    grade: str
    avg_chars: int         # 조각당 평균 — 참고용(판정에는 안 쓴다)
    chars_per_page: int    # 페이지당 본문 글자수 — 실제 판정 기준
    coverage: int          # 0~100 (%)
    segment_count: int
    page_count: int
    empty_segments: list[int]
    reason: str

    @property
    def is_body(self) -> bool:
        return self.grade == DensityGrade.FULL.value


def measure(
    segments: list[Segment],
    *,
    empty_segments: list[int],
    failed_segments: list[int] | None = None,
) -> DensityReport:
    """조각과 개념 부착 현황으로 밀도 등급을 매긴다.

    empty_segments — 개념이 하나도 안 나온 조각
    failed_segments — 추출 호출 자체가 실패한 조각. 자료 탓이 아니므로
                      커버리지에서 **분모·분자 모두 제외**한다. 안 그러면
                      일시적인 API 오류가 자료를 '뼈대만'으로 강등시킨다.
    """
    if not segments:
        return DensityReport(
            grade=DensityGrade.SKELETON.value,
            avg_chars=0, chars_per_page=0, coverage=0, segment_count=0,
            page_count=0, empty_segments=[], reason="조각 없음",
        )

    failed = set(failed_segments or [])
    counted = [s for s in segments if s.seq not in failed]
    if not counted:
        counted = segments

    avg_chars = sum(s.char_count for s in counted) // len(counted)
    empty = [seq for seq in empty_segments if seq not in failed]
    coverage = round((len(counted) - len(empty)) * 100 / len(counted))

    # 페이지 수는 조각이 실제로 덮은 범위로 센다. 정제로 걷어낸 표지·목차
    # 페이지까지 분모에 넣으면 멀쩡한 교재가 얇아 보인다.
    pages = {p for s in counted for p in (s.page_from, s.page_to) if p is not None}
    page_count = (max(pages) - min(pages) + 1) if pages else 0
    total_chars = sum(s.char_count for s in counted)
    chars_per_page = total_chars // page_count if page_count else total_chars

    thin = chars_per_page < BODY_MIN_CHARS_PER_PAGE
    sparse = coverage < BODY_MIN_COVERAGE
    if thin and sparse:
        reason = f"페이지가 얇고({chars_per_page}자/p) 개념도 드묾({coverage}%)"
    elif thin:
        reason = (
            f"페이지당 {chars_per_page}자 — 기준 {BODY_MIN_CHARS_PER_PAGE}자 미만"
        )
    elif sparse:
        reason = f"개념 커버리지 {coverage}% — 기준 {BODY_MIN_COVERAGE}% 미만"
    else:
        reason = f"페이지당 {chars_per_page}자 · 커버리지 {coverage}%"

    grade = (
        DensityGrade.SKELETON.value
        if thin or sparse
        else DensityGrade.FULL.value
    )

    report = DensityReport(
        grade=grade,
        avg_chars=avg_chars,
        chars_per_page=chars_per_page,
        coverage=coverage,
        segment_count=len(segments),
        page_count=page_count,
        empty_segments=empty,
        reason=reason,
    )
    _log.info(
        "밀도 판정: %s — %s (조각 %d개 · %d페이지 · 조각당 %d자, 추출 실패 %d개 제외)",
        "본문 가능" if report.is_body else "뼈대만",
        reason, len(segments), page_count, avg_chars, len(failed),
    )
    return report
