"""spans 단위 테스트 — 생성의 입력 단위를 쪼개는 로직.

여기가 틀리면 커버리지 보장이 무너진다. span 방식의 전제는 "전 구간을 돌면
원문 전체가 다뤄진다"이므로, 분할이 원문을 흘리면 전제 자체가 거짓이 된다.
그래서 (1) 원문 표기 보존 (2) 내용 누락 없음 (3) 쌍 수 폭증 방지를 검사한다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.problems import spans  # noqa: E402
from app.features.problems.coverage import _HEADING_RE  # noqa: E402
from app.features.problems.grounding import (  # noqa: E402
    evidence_in_source,
    normalize,
)

SOURCE = """### ■ 기억장치 관리 전략

| **전략** | **종류** | **설명** |
| --- | --- | --- |
| **배치 전략** | **최초 적합**

(First Fit) | 사용 가능한 '첫 번째' 분할 영역에 데이터 배치 |
|  | **최적 적합**

(Best Fit) | 단편화를 '최소화'하는 분할 영역에 데이터 배치 |
|  | **최악 적합**

(Worst Fit) | 단편화를 '최대화'하는 분할 영역에 데이터 배치 |

### ■ 페이지 교체 알고리즘

| **OPT** | • 앞으로 가장 오랫동안 사용하지 않을 페이지를 교체 |
| **FIFO** | • 가장 먼저 들어와 가장 오래 있었던 페이지를 교체 |
| **LRU** | • 최근에 가장 오랫동안 사용하지 않은 페이지를 교체 |
| **LFU** | • 사용 빈도가 가장 적은 페이지를 교체 |"""


def test_splits_into_multiple_spans():
    result = spans.split(SOURCE)
    # 한 덩어리로 남으면 "한 번에 너무 큰 것을 요구한다"는 문제가 그대로다.
    assert len(result) >= 4, f"구간이 {len(result)}개뿐"


def test_span_text_is_verbatim():
    # 구간 텍스트는 근거 대조의 대상이다. 가공하면 게이트가 전부 오작동한다.
    for s in spans.split(SOURCE):
        assert evidence_in_source(s.text, SOURCE), f"구간 {s.index}이 원문에 없음"


def test_no_content_is_dropped():
    # 분할이 원문을 흘리면 "전 구간 순회 = 전체 커버"가 거짓이 된다.
    joined = normalize("\n".join(s.text for s in spans.split(SOURCE)))
    for line in SOURCE.splitlines():
        text = normalize(line)
        if not text or _HEADING_RE.match(line) or set(line.strip()) <= set("|-: "):
            continue  # 제목·표 구분행은 heading으로 가거나 내용이 아니다
        assert text in joined, f"누락된 줄: {line!r}"


def test_heading_is_attached_not_emitted():
    result = spans.split(SOURCE)
    # 제목 자체는 출제 근거가 못 되므로 span이 되지 않는다.
    assert all(not s.text.lstrip().startswith("###") for s in result)
    # 대신 맥락으로 붙는다.
    assert any("기억장치" in s.heading for s in result)
    assert any("페이지 교체" in s.heading for s in result)


def test_spans_are_not_too_short():
    # 너무 짧은 조각은 한 문항을 만들 재료가 못 된다(마지막 조각만 예외).
    result = spans.split(SOURCE)
    for s in result[:-1]:
        assert s.length >= spans.MIN_SPAN_CHARS // 2, f"구간 {s.index} 너무 짧음"


def test_table_rows_are_not_cut_in_half():
    # 회귀 방지(실측): 길이만 보고 끊어 "**최적 적합**"과 "단편화를 '최소화'…"가
    # 다른 구간으로 갈라졌다. 용어와 설명이 떨어지면 어느 쪽으로도 출제할 수 없다.
    for s in spans.split(SOURCE):
        text = normalize(s.text)
        for term, desc in [
            ("최적 적합", "최소화"),
            ("최악 적합", "최대화"),
            ("FIFO", "가장 먼저 들어와"),
            ("LFU", "사용 빈도가 가장 적은"),
        ]:
            if term in text or desc in text:
                assert term in text and desc in text, f"구간 {s.index}에서 {term} 분리"


def test_closes_unit_rule():
    assert spans._closes_unit("| **OPT** | 앞으로 오래 쓰지 않을 페이지 |")
    assert not spans._closes_unit("| **최적 적합**")  # 표 행 중간
    assert spans._closes_unit("산문 한 줄이다")


def test_oversized_row_is_still_split():
    # 표가 깨져 행 끝(`|`)이 영영 안 오면 구간 하나가 무한정 커진다.
    broken = "\n".join(f"| 항목{i} 설명이 길게 이어진다" for i in range(60))
    result = spans.split(broken)
    assert len(result) > 1
    assert all(s.length <= spans.MAX_SPAN_CHARS * 1.2 for s in result)


def test_empty_source_yields_nothing():
    assert spans.split("") == []
    assert spans.split("### 제목만 있다\n\n| --- |") == []


def fake(count: int, heading: str = "표") -> list[spans.Span]:
    return [spans.Span(index=i, heading=heading, text=f"본문{i}") for i in range(count)]


def test_pair_indices_are_adjacent():
    assert spans.pair_indices(fake(4), 10) == [(0, 1), (1, 2), (2, 3)]


def test_pair_indices_respects_limit():
    # 조합 폭증 방지 — 구간 16개면 인접 쌍만 15개, 전체 조합은 120개다.
    pairs = spans.pair_indices(fake(16), 3)
    assert len(pairs) == 3
    assert all(b == a + 1 for a, b in pairs)
    # 앞부분에만 몰리지 않아야 원문 전체가 심화 문항의 대상이 된다.
    assert pairs[-1][0] > 7


def test_pairs_stay_inside_one_heading():
    # 회귀 방지(실측 L3=0): 서로 다른 표의 행을 비교시키면 비교할 축이 없어
    # 모델이 빈 배열을 돌려준다.
    items = fake(2, "표A") + [
        spans.Span(index=2, heading="표B", text="본문2"),
        spans.Span(index=3, heading="표B", text="본문3"),
    ]
    assert spans.pair_indices(items, 10) == [(0, 1), (2, 3)]


def test_pairs_fall_back_when_headings_all_differ():
    # 제목 없는 산문이면 같은 제목 쌍이 하나도 없다 — 인접 쌍으로 돌아간다.
    items = [spans.Span(index=i, heading=f"h{i}", text="x") for i in range(3)]
    assert spans.pair_indices(items, 10) == [(0, 1), (1, 2)]


def test_pair_indices_degenerate():
    assert spans.pair_indices(fake(1), 5) == []
    assert spans.pair_indices([], 5) == []
    assert spans.pair_indices(fake(5), 0) == []


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
