"""quality.is_free_response_style 단위 테스트.

회귀 방지 대상: 프롬프트에 "서술형 지시문 금지"를 넣었는데도 L3 문항이
"…비교하여 설명하시오"로 생성되던 문제(실측). 보기 4개를 주면서 서술을
요구하는 건 형식 모순이라 코드에서 확정 차단한다.
동시에 '설명'이 명사로 쓰인 정상 지문을 오폐기하지 않아야 한다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.problems.quality import is_free_response_style  # noqa: E402


def test_free_response_endings_rejected():
    # 실제 생성된 위반 사례 2건(운영체제 L3).
    assert is_free_response_style("페이징 기법과 세그먼테이션 기법을 비교하여 설명하시오.")
    assert is_free_response_style(
        "페이지 교체 알고리즘 OPT와 LRU의 공통점과 차이점을 원문의 설명을 바탕으로 서술하시오."
    )


def test_various_endings_rejected():
    for q in (
        "반입 전략의 종류를 나열하시오",
        "최적 적합의 정의를 쓰시오.",
        "다음 알고리즘의 동작을 기술하라",
        "페이지 부재 횟수를 구하시오?",
    ):
        assert is_free_response_style(q), q


def test_selection_style_passes():
    # 정상적인 객관식 지문 — 통과해야 한다.
    for q in (
        "다음 중 기아(starvation)가 발생할 수 있는 스케줄링은?",
        "OPT 알고리즘의 설명으로 옳은 것은?",
        "세그먼테이션 기법에서 발생할 수 있는 단편화는 무엇인가?",
        "페이지 크기가 작을 때의 단점에 해당하는 것은?",
    ):
        assert not is_free_response_style(q), q


def test_noun_form_not_confused():
    # '설명'이 명사로 쓰인 경우를 서술형으로 오판하면 안 된다.
    assert not is_free_response_style("다음 설명 중 옳지 않은 것은?")


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
