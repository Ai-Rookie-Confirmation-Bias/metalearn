"""service의 순수 로직 단위 테스트 — LLM 호출 없이 검증 가능한 부분.

주 대상은 `_select`: 레벨 상한을 지키면서 슬롯을 **구간에 고루** 배분하는 규칙.
도착 순서대로 채우면 앞 구간이 슬롯을 다 먹어 원문 뒷부분이 통째로 빠지고,
그러면 span 분할로 얻으려던 커버리지 보장이 사라진다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.problems.schemas import Problem, ProblemType  # noqa: E402
from app.features.problems.service import _select  # noqa: E402


def make(question: str, level: int) -> Problem:
    return Problem(
        level=level,
        type=ProblemType.MCQ,
        question=question,
        options=["가", "나", "다", "라"],
        answer="가",
        explanation="해설",
        source_evidence="근거",
    )


def test_slots_spread_across_spans():
    # 구간 0이 3문항, 구간 1·2가 1문항씩. 상한 2에 도착 순서대로 채우면
    # 구간 0만 남지만, 라운드로빈이면 구간 0·1이 한 문항씩 가져간다.
    candidates = [
        (make("s0-a", 1), 1, 0),
        (make("s0-b", 1), 1, 0),
        (make("s0-c", 1), 1, 0),
        (make("s1-a", 1), 1, 1),
        (make("s2-a", 1), 1, 2),
    ]
    picked = [p.question for p in _select(candidates, 2)[1]]
    assert picked == ["s0-a", "s1-a"], picked


def test_respects_per_level_cap():
    candidates = [(make(f"q{i}", 1), 1, i) for i in range(10)]
    assert len(_select(candidates, 3)[1]) == 3


def test_levels_are_independent():
    candidates = [
        (make("l1", 1), 1, 0),
        (make("l2", 2), 2, 1),
        (make("l3", 3), 3, 2),
    ]
    by_level = _select(candidates, 1)
    assert [len(by_level[lv]) for lv in (1, 2, 3)] == [1, 1, 1]


def test_downgraded_problem_gets_extra_room():
    # 회귀 방지(실측 18→10): L2로 요청했다 L1으로 강등된 문항이 이미 찬 L1
    # 슬롯과 경쟁해 버려졌다. 강등분은 상한 두 배까지 받아준다.
    candidates = [
        (make("native-1", 1), 1, 0),
        (make("native-2", 1), 1, 1),
        (make("downgraded", 1), 2, 2),  # L2로 요청 → L1로 강등
    ]
    picked = [p.question for p in _select(candidates, 2)[1]]
    assert "downgraded" in picked, picked


def test_duplicate_questions_are_dropped():
    # 구간이 겹치는 내용을 담으면 같은 질문이 두 번 나올 수 있다.
    candidates = [
        (make("같은 질문", 1), 1, 0),
        (make("같은  질문", 1), 1, 1),  # 공백만 다르다
    ]
    assert len(_select(candidates, 5)[1]) == 1


def test_empty_input():
    by_level = _select([], 3)
    assert by_level == {1: [], 2: [], 3: []}


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
