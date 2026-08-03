"""성향 프로파일 단위 테스트.

핵심 회귀 대상 셋:
  ① 확신 없으면 지시가 안 나간다 — 잘못 잰 성향으로 미는 게 더 손해다
  ② 화면 문구와 프롬프트 지시가 같은 조건으로 나온다 — 어긋나면 거짓말이 된다
  ③ 같은 관찰이면 같은 결과 — 그래야 "왜 이렇게 설명했는지"를 고정해 쓸 수 있다
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.curriculum.profile import (  # noqa: E402
    AXES,
    LOW,
    MIN_CONFIDENCE,
    AxisScore,
    as_display,
    directives,
    empty_profile,
    explain,
    observe,
    prompt_block,
)


def _observe_many(axis: str, toward_high: bool, times: int):
    p = empty_profile()
    for _ in range(times):
        p = observe(p, axis, toward_high)
    return p


def test_처음엔_아무_지시도_없다():
    # 측정 전에 성향을 가정하면 안 된다.
    assert directives(empty_profile()) == []
    assert prompt_block(empty_profile()) == ""


def test_한_번_관찰로는_발동하지_않는다():
    # 1회는 우연일 수 있다. confidence 0.3 < MIN_CONFIDENCE 0.35
    p = _observe_many("representation", True, 1)
    assert p["representation"].confidence < MIN_CONFIDENCE
    assert directives(p) == []


def test_두_번_같은_방향이면_발동한다():
    p = _observe_many("representation", True, 2)
    s = p["representation"]
    assert s.confidence >= MIN_CONFIDENCE, s
    assert s.score > 0.6, s
    assert any("비유" in d for d in directives(p)), directives(p)


def test_반대_방향이면_반대_지시가_나간다():
    p = _observe_many("representation", False, 2)
    ds = directives(p)
    assert any("정의와 형식을 먼저" in d for d in ds), ds
    assert not any("비유나 구체적 예시를 정의보다 먼저" in d for d in ds), ds


def test_엇갈리면_중립이다():
    # A→B→A→B 처럼 갈리면 성향이 없는 것이다. 억지로 밀지 않는다.
    p = empty_profile()
    for toward in (True, False, True, False):
        p = observe(p, "representation", toward)
    s = p["representation"]
    assert LOW <= s.score <= 0.6, s
    assert directives(p) == []


def test_축은_서로_독립이다():
    p = _observe_many("representation", True, 2)
    assert p["depth"].n == 0
    assert len(directives(p)) == 1


def test_두_축이_다_잡히면_지시도_둘():
    p = _observe_many("representation", True, 2)
    for _ in range(2):
        p = observe(p, "depth", True)
    assert len(directives(p)) == 2
    block = prompt_block(p)
    assert "비유" in block and "왜 그렇게 되는지" in block


def test_화면_문구와_프롬프트_지시가_일치한다():
    # 화면엔 "비유로 설명합니다"라고 써놓고 프롬프트엔 안 넣으면 거짓말이다.
    for toward in (True, False):
        p = _observe_many("depth", toward, 2)
        assert len(explain(p)) == len(directives(p))
    assert explain(empty_profile()) == []


def test_결정적이다():
    a = _observe_many("depth", True, 3)
    b = _observe_many("depth", True, 3)
    assert a == b


def test_점수는_0과_1_사이를_벗어나지_않는다():
    p = _observe_many("depth", True, 20)
    assert 0.0 <= p["depth"].score <= 1.0
    p = _observe_many("depth", False, 20)
    assert 0.0 <= p["depth"].score <= 1.0


def test_모르는_축은_거부한다():
    try:
        observe(empty_profile(), "없는축", True)
    except KeyError:
        return
    raise AssertionError("모르는 축을 받아들였다")


def test_표시용_데이터에_신뢰도_낮은_축도_나온다():
    # 숨기면 사용자가 왜 어떤 축만 반영됐는지 알 수 없다.
    p = _observe_many("representation", True, 1)
    rows = as_display(p)
    assert len(rows) == len(AXES)
    rep = next(r for r in rows if r["key"] == "representation")
    assert rep["active"] is False and rep["n"] == 1


def test_학습_중_성향이_바뀌면_따라간다():
    # 초기 판단이 틀렸을 수 있다. 최근 관찰에 무게를 둔다.
    p = _observe_many("representation", True, 2)
    assert p["representation"].score > 0.6
    for _ in range(6):
        p = observe(p, "representation", False)
    assert p["representation"].score < LOW, p["representation"]


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
