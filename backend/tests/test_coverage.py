"""coverage 단위 테스트 — 원문 커버리지 측정과 미커버 피드백.

회귀 방지 대상: 문항 수와 근거 정확도는 정상인데 원문 한구석만 파고들어
"이 개념을 다 공부했는가"가 성립하지 않는 상태. 게이트 ①~④로는 안 잡힌다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.problems import coverage  # noqa: E402

SOURCE = """### ■ 페이지 교체 알고리즘

| **알고리즘** | **설명** |
| --- | --- |
| **OPT** | • 앞으로 가장 오랫동안 사용하지 않을 페이지를 교체 |
| **FIFO** | • 가장 먼저 들어와 가장 오래 있었던 페이지를 교체 |
| **LRU** | • 최근에 가장 오랫동안 사용하지 않은 페이지를 교체 |
| **LFU** | • 사용 빈도가 가장 적은 페이지를 교체 |
"""


def test_no_evidence_means_zero_coverage():
    r = coverage.analyze([], SOURCE)
    assert r.ratio == 0.0
    assert r.covered_lines == 0
    assert r.total_lines > 0


def test_table_rule_row_excluded():
    # `| --- | --- |` 구분행은 내용이 아니므로 분모에서 빠져야 한다.
    r = coverage.analyze([], SOURCE)
    assert not any(set(line) <= set("| -") for line in r.uncovered)


def test_partial_quote_covers_line():
    # 한 줄의 일부만 인용해도 그 줄은 커버로 센다(중복 출제 유도 방지).
    r = coverage.analyze(["앞으로 가장 오랫동안 사용하지 않을 페이지를 교체"], SOURCE)
    assert r.covered_lines == 1
    assert not any("OPT" in line for line in r.uncovered)


def test_full_coverage():
    # 제목("### ■ …")은 분모에서 빠지므로 표 4행만 덮으면 100%다.
    evidences = [
        "앞으로 가장 오랫동안 사용하지 않을 페이지를 교체",
        "가장 먼저 들어와 가장 오래 있었던 페이지를 교체",
        "최근에 가장 오랫동안 사용하지 않은 페이지를 교체",
        "사용 빈도가 가장 적은 페이지를 교체",
    ]
    r = coverage.analyze(evidences, SOURCE)
    assert r.ratio == 1.0 and r.uncovered == []


def test_headings_excluded_from_denominator():
    # 제목은 출제 대상이 아니다 — 분모에도 미커버 목록에도 없어야 한다.
    r = coverage.analyze([], SOURCE)
    assert not any(line.lstrip().startswith("#") for line in r.uncovered)

    bold_heading_src = "**1) 페이징 기법 (Paging)**\n\n- 동일 크기로 분할하는 기법이다\n"
    r2 = coverage.analyze([], bold_heading_src)
    assert r2.total_lines == 1  # 굵은 소제목 제외, 본문 1줄만


def test_uncovered_returns_original_markdown():
    # 피드백에 원문 표기 그대로 실려야 LLM이 그 구간을 찾아 출제할 수 있다.
    r = coverage.analyze(["앞으로 가장 오랫동안 사용하지 않을 페이지를 교체"], SOURCE)
    assert any("FIFO" in line and "|" in line for line in r.uncovered)


def test_feedback_text_lists_uncovered():
    r = coverage.analyze(["앞으로 가장 오랫동안 사용하지 않을 페이지를 교체"], SOURCE)
    text = coverage.feedback_text(r)
    assert "커버리지" in text and "LFU" in text


def test_feedback_empty_when_fully_covered():
    r = coverage.CoverageReport(1.0, 5, 5, [])
    assert coverage.feedback_text(r) == ""


def test_percent_rounds():
    assert coverage.CoverageReport(0.666, 2, 3, []).percent == 67


def _main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}  {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_main())
