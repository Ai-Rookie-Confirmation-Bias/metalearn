"""levels 단위 테스트 — 레벨 라벨이 실제 난이도와 맞는지 판정.

회귀 방지 대상(실측): 모든 게이트를 통과했지만 근거 한 줄을 그대로 되묻는
문항이 L3로 태깅돼 있었다. 레벨 사이에 실제 난이도 차이가 없으면 레벨
게이트("L1 80% 통과해야 L2 언락")가 껍데기가 된다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.problems import levels  # noqa: E402
from app.features.problems.schemas import ProblemType  # noqa: E402

SOURCE = """### ■ 기억장치 관리 전략

| **배치 전략** | **최초 적합**

(First Fit) | 사용 가능한 '첫 번째' 분할 영역에 데이터 배치 |
|  | **최적 적합**

(Best Fit) | 단편화를 '최소화'하는 분할 영역에 데이터 배치 |
|  | **최악 적합**

(Worst Fit) | 단편화를 '최대화'하는 분할 영역에 데이터 배치 |
"""


def test_answer_verbatim_in_evidence_is_level1():
    # 실측 오분류 사례 — 근거를 읽으면 답이 그대로 보인다.
    assert (
        levels.assess(
            ProblemType.MCQ,
            "단편화를 최대화",
            "단편화를 '최대화'하는 분할 영역에 데이터 배치",
            SOURCE,
        )
        == 1
    )


def test_term_to_description_mapping_is_level2():
    # 용어↔설명 매핑이 필요하면 단순 재인이 아니다.
    assert (
        levels.assess(
            ProblemType.MCQ,
            "Best Fit",
            "단편화를 '최소화'하는 분할 영역에 데이터 배치",
            SOURCE,
        )
        == 2
    )


def test_two_location_synthesis_is_level3():
    # 서로 다른 두 곳을 종합해야 풀리는 문항.
    assert (
        levels.assess(
            ProblemType.MCQ,
            "최초 적합은 첫 번째 영역, 최적 적합은 단편화 최소 영역에 배치",
            "사용 가능한 '첫 번째' 분할 영역에 데이터 배치\n"
            "단편화를 '최소화'하는 분할 영역에 데이터 배치",
            SOURCE,
        )
        == 3
    )


def test_two_locations_but_answer_visible_is_level1():
    # 두 곳을 인용했어도 정답이 근거에 그대로 있으면 종합이 아니다.
    assert (
        levels.assess(
            ProblemType.MCQ,
            "단편화를 최소화하는 분할 영역에 데이터 배치",
            "사용 가능한 '첫 번째' 분할 영역에 데이터 배치\n"
            "단편화를 '최소화'하는 분할 영역에 데이터 배치",
            SOURCE,
        )
        == 1
    )


def test_answer_visible_helper():
    assert levels.answer_visible_in_evidence(
        "단편화를 최대화", "단편화를 '최대화'하는 분할 영역에 데이터 배치"
    )
    # 마크다운 장식·따옴표 차이는 흡수한다.
    assert levels.answer_visible_in_evidence(
        "최초 적합", "| **최초 적합** | 사용 가능한 '첫 번째' 분할 영역"
    )
    assert not levels.answer_visible_in_evidence(
        "Best Fit", "단편화를 '최소화'하는 분할 영역에 데이터 배치"
    )
    assert not levels.answer_visible_in_evidence("", "아무 근거")


def test_multi_is_not_downgraded_to_level1():
    # 실측 회귀: "배치 전략에 해당하는 것을 모두 고르시오"가 정답 항목이 전부
    # 원문에 있다는 이유로 L1으로 강등됐다. 범주 판단이 필요하므로 L2 이상이다.
    assert (
        levels.assess(
            ProblemType.MULTI,
            ["최초 적합", "최적 적합", "최악 적합"],
            "최초 적합\n최적 적합\n최악 적합",
            SOURCE,
        )
        >= 2
    )


def test_order_is_not_downgraded_to_level1():
    assert (
        levels.assess(
            ProblemType.ORDER,
            ["최초 적합", "최적 적합"],
            "사용 가능한 '첫 번째' 분할 영역에 데이터 배치",
            SOURCE,
        )
        >= 2
    )


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
