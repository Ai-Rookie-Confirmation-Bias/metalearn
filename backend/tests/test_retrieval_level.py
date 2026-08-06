"""인출 수준 판정 단위 테스트.

모델이 붙인 라벨은 자기 신고라 못 믿는다 — 실측에서 `kind="상황"`이라고 답한
문항 4개가 정의문을 그대로 옮긴 것이었고(겹침 0.97), `kind="성질"` 2개도
마찬가지였다. 13개 중 6개가 거짓 신고였다. 그걸 기계로 잡는 게 이 모듈이다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.curriculum.retrieval_level import (  # noqa: E402
    L1_RECALL,
    L2_APPLY,
    L3_DISCRIMINATE,
    assess_cloze,
    assess_mcq,
    mix,
    overlap,
)

DEF = "절차 지향 방식으로 최상위 컴포넌트를 먼저 설계한 뒤 하위 기능을 부여하는 설계 방법"


def test_정의문을_그대로_옮기면_재인이다():
    # 실측 사고: kind="상황"이라 신고했지만 겹침 0.97이었다.
    copied = "어떤 팀이 절차 지향 방식으로 최상위 컴포넌트를 먼저 설계한 뒤 하위 기능을 부여하는 설계 방식으로 일한다면 ____ 다."
    assert assess_cloze(copied, DEF) == L1_RECALL


def test_다른_말로_바꾸면_적용이다():
    reworded = "큰 그림을 먼저 잡고 아래로 내려가며 채우는 방식을 ____ 라 한다."
    assert assess_cloze(reworded, DEF) == L2_APPLY


def test_잴_수_없으면_강등하지_않는다():
    # 강등은 근거가 있을 때만. 정의가 없다고 낮게 잡으면 멀쩡한 문항이 깎인다.
    assert assess_cloze("무언가를 ____ 라 한다.", "") == L2_APPLY
    assert assess_cloze("", DEF) == L2_APPLY


def test_객관식은_보기에_절_개념이_여럿이어야_구별이다():
    keys = ["하향식 설계", "상향식 설계"]
    both = ["하향식 설계", "상향식 설계", "폭포수 모형", "나선형 모형"]
    assert assess_mcq(both, keys) == L3_DISCRIMINATE

    # 절 개념이 하나뿐이면 나머지는 절 밖 들러리라 빈칸과 다를 게 없다.
    one = ["하향식 설계", "폭포수 모형", "나선형 모형", "애자일 모형"]
    assert assess_mcq(one, keys) == L2_APPLY


def test_겹침은_방향이_있다():
    # a가 b에 얼마나 담겼는지를 본다 — 정의(짧음)가 문항(김)에 담겼는지가 관심사다.
    assert overlap("최상위 컴포넌트", "최상위 컴포넌트를 먼저 설계한다") == 1.0
    assert overlap("전혀 다른 말", "최상위 컴포넌트를 먼저 설계한다") < 0.3


def test_분포를_센다():
    assert mix([1, 1, 2, 3]) == {"L1": 2, "L2": 1, "L3": 1}


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
