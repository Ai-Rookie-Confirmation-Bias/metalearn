"""[순수로직] 원문 커버리지 — 문항이 원문의 어느 부분을 출제했는가.

DB·LLM 비의존. 게이트 ①~④가 "나쁜 문항을 버리는" 장치라면, 커버리지는
**좋은 문항이 빠짐없이 나오게 하는** 장치다.

왜 필요한가: 원문 1500자를 주면 LLM은 눈에 띄는 표 하나를 집중적으로 파고
나머지를 건드리지 않는 경향이 있다. 문항 수와 근거 정확도만 보면 정상으로
보이지만, 문제은행으로서는 "이 개념을 다 공부했는가"를 보장하지 못한다.
학습 완료 판정이 커버리지 위에 서 있으므로 측정 대상이어야 한다.

측정 단위는 **원문 줄**이다(정규화된 문자열 위치가 아니라):
  · 표 셀·불릿과 자연스럽게 맞아떨어진다
  · 미커버 구간을 **원문 그대로** 뽑아 재시도 프롬프트에 넣을 수 있다
    → 측정에서 끝나지 않고 자기수정 루프에 바로 연결된다

관대한 판정: 한 줄의 일부만 인용해도 그 줄을 커버로 센다. 목적이 "아직
손대지 않은 구간 찾기"이므로 부분 인용을 미커버로 몰아 재출제를 유도하면
같은 내용을 중복 출제하게 된다.
"""
import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.features.problems.grounding import normalize

# 이보다 짧은 줄은 구분자·잔재로 보고 커버리지 분모에서 뺀다.
MIN_LINE_CHARS = 10

# 제목 줄은 출제 대상이 아니므로 분모에서 뺀다. 넣어두면 영원히 미커버로
# 남아 커버리지가 실제보다 낮게 나오고, 재시도가 제목을 출제하려 든다.
_HEADING_RE = re.compile(
    r"""^\s*(?:
        \#{1,6}\s          # 마크다운 제목  "### 제목"
      | \*\*[^*]+\*\*\s*$  # 통째로 굵게 쓴 소제목  "**1) 페이징 기법**"
    )""",
    re.VERBOSE,
)
# 재시도 피드백에 실을 미커버 줄 수·길이 상한(프롬프트 비대화 방지).
_FEEDBACK_LINES = 6
_FEEDBACK_LINE_CHARS = 160


@dataclass(frozen=True)
class CoverageReport:
    ratio: float  # 0.0~1.0 — 커버된 내용 분량 비율
    covered_lines: int
    total_lines: int
    uncovered: list[str]  # 미커버 원문 줄(원문 표기 그대로)

    @property
    def percent(self) -> int:
        return round(self.ratio * 100)


def _content_lines(source: str) -> list[tuple[str, str]]:
    """(원문 줄, 정규화 줄) — 표 구분행·빈 줄·짧은 줄·제목은 제외.

    normalize()가 표 구분행(`| --- |`)을 빈 문자열로 만들므로 자연히 걸러진다.
    제목은 별도로 판별해 뺀다(설명이 아니라 이름표라 출제 근거가 못 된다).
    """
    out: list[tuple[str, str]] = []
    for raw in source.splitlines():
        if _HEADING_RE.match(raw):
            continue
        norm = normalize(raw)
        if len(norm) >= MIN_LINE_CHARS:
            out.append((raw.strip(), norm))
    return out


def analyze(evidences: Sequence[str], source: str) -> CoverageReport:
    """근거 목록이 원문의 어느 정도를 덮는지 계산한다."""
    lines = _content_lines(source)
    if not lines:
        return CoverageReport(1.0, 0, 0, [])

    norm_evidences = [normalize(e) for e in evidences if e]
    covered_chars = total_chars = 0
    covered_n = 0
    uncovered: list[str] = []

    for raw, norm in lines:
        total_chars += len(norm)
        # 줄이 근거에 통째로 담겼거나(여러 줄 인용), 근거가 그 줄의 일부이거나.
        if any(norm in ev or ev in norm for ev in norm_evidences):
            covered_chars += len(norm)
            covered_n += 1
        else:
            uncovered.append(raw)

    ratio = covered_chars / total_chars if total_chars else 1.0
    return CoverageReport(ratio, covered_n, len(lines), uncovered)


def feedback_text(report: CoverageReport) -> str:
    """미커버 구간을 다음 시도 프롬프트용 지시로 만든다(없으면 빈 문자열)."""
    if not report.uncovered:
        return ""
    picked = sorted(report.uncovered, key=len, reverse=True)[:_FEEDBACK_LINES]
    quoted = "\n".join(f"  - {line[:_FEEDBACK_LINE_CHARS]}" for line in picked)
    return (
        f"원문 커버리지가 {report.percent}%다. 아직 출제되지 않은 아래 구간에서 "
        f"출제하라(이미 다룬 내용의 재출제 금지):\n{quoted}"
    )
