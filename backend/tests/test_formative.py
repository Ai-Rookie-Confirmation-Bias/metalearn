"""형성평가의 순수 부분 — 무엇을 고르는가, 무엇을 가로지름으로 세는가.

LLM은 안 부른다. 잠그는 건 **재는 기준**이다. 인출에서 배웠듯 프롬프트로
요구만 하면 안 지켜지고, 그래서 재는 쪽이 정확해야 게이트가 일한다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.curriculum.agents.formative import (  # noqa: E402
    build_prompt,
    crossing,
    select_concepts,
)
from app.features.curriculum.blocks import (  # noqa: E402
    _TEMPLATE_MARKERS,
    Block,
    ConceptBrief,
)
from app.features.curriculum.mastery import ChapterMastery  # noqa: E402
from app.features.curriculum.planner import (  # noqa: E402
    FORMATIVE_UNLOCK,
    formative_ready,
)

A1, A2 = ConceptBrief("자료 결합도", "자료만 주고받음"), ConceptBrief("제어 결합도", "제어 신호")
B1, B2 = ConceptBrief("기능적 응집도", "한 기능"), ConceptBrief("논리적 응집도", "비슷한 것끼리")
C1 = ConceptBrief("모듈", "분리된 기능 단위")

# (화면 제목, 개념들, 시도 횟수)
SCREENS = [("결합도", (A1, A2), 4), ("응집도", (B1, B2), 0), ("모듈", (C1,), 2)]


def _mcq(options: list[str]) -> Block:
    return Block("mcq", {"question": "?", "options": options, "answer": options[0]})


SCREEN_OF = {c.key: i for i, (_t, cs, _a) in enumerate(SCREENS) for c in cs}


# ── 가로지름 판정 ──────────────────────────────────────────────────


def test_다른_화면_개념이_섞이면_가로지름():
    assert crossing(_mcq(["자료 결합도", "기능적 응집도"]), SCREEN_OF)


def test_같은_화면_개념만이면_아니다():
    # 이러면 이미 푼 인출 문항과 다를 게 없다.
    assert not crossing(_mcq(["자료 결합도", "제어 결합도"]), SCREEN_OF)


def test_모르는_보기는_안_센다():
    # 모델이 지어낸 보기로 "가로질렀다"가 되면 게이트가 헐거워진다.
    assert not crossing(_mcq(["자료 결합도", "듣도보도 못한 것"]), SCREEN_OF)


def test_빈칸은_가로지름이_아니다():
    # 빈칸은 개념 하나를 꺼내는 것이라 구별을 못 잰다.
    b = Block("cloze", {"sentence": "____ 다", "answer": "모듈"})
    assert not crossing(b, SCREEN_OF)


# ── 무엇을 물을지 고르기 ───────────────────────────────────────────


def test_약점을_가장_먼저_고른다():
    # 약점을 확인하지 않는 평가는 평가가 아니다.
    picked = select_concepts(SCREENS, ("논리적 응집도",), limit=1)
    assert [c.key for c in picked] == ["논리적 응집도"]


def test_약점_다음은_안_풀어본_화면():
    # 미측정 자리는 숙련도에 구멍으로 남아 있다.
    picked = select_concepts(SCREENS, (), limit=2)
    assert {c.key for c in picked} == {"기능적 응집도", "논리적 응집도"}  # 시도 0인 화면


def test_중복은_한_번만():
    picked = select_concepts(SCREENS, ("자료 결합도", "자료 결합도"), limit=9)
    keys = [c.key for c in picked]
    assert len(keys) == len(set(keys))


def test_한도를_지킨다():
    assert len(select_concepts(SCREENS, (), limit=3)) == 3


def test_전부_고르면_모든_개념이_들어간다():
    picked = select_concepts(SCREENS, (), limit=99)
    assert len(picked) == 5


# ── 프롬프트 ───────────────────────────────────────────────────────


def test_프롬프트가_화면별로_묶어_준다():
    # 평평하게 나열하면 어느 게 같이 배운 것인지 몰라 가로지를 수가 없다.
    p = build_prompt("설계", [(t, cs) for t, cs, _ in SCREENS], [A1, B1])
    assert "[화면 1] 결합도" in p and "[화면 2] 응집도" in p
    assert "자료 결합도" in p and "기능적 응집도" in p


def test_안_고른_개념은_프롬프트에_없다():
    p = build_prompt("설계", [(t, cs) for t, cs, _ in SCREENS], [A1])
    assert "제어 결합도" not in p


def test_약점은_반드시_넣으라고_한다():
    p = build_prompt("설계", [(t, cs) for t, cs, _ in SCREENS], [A1], ("모듈",))
    assert "모듈" in p and "반드시" in p


def test_예시_문항이_필터를_통과한다():
    """예시가 곧 출력이다. 예시가 파서에 걸리면 베낀 문항이 통째로 버려진다.

    실측: 예시 질문을 `"다음 설명에 해당하는 것은?"`으로 뒀더니 그게
    `_TEMPLATE_MARKERS`라 **0문항**이 나왔다.
    """
    p = build_prompt("설계", [(t, cs) for t, cs, _ in SCREENS], [A1, B1])
    for marker in _TEMPLATE_MARKERS:
        assert marker not in p, marker


def test_예시_보기가_화면을_가로지른다():
    # 베껴도 우리가 원하는 모양이어야 한다.
    p = build_prompt("설계", [(t, cs) for t, cs, _ in SCREENS], [A1, B1, C1])
    assert '"options"' in p
    assert "자료 결합도" in p and "기능적 응집도" in p


# ── 잠금 ───────────────────────────────────────────────────────────


def _summary(total: int, touched: int) -> ChapterMastery:
    return ChapterMastery("1장", total, touched, 0.0, ())


def test_진도가_모자라면_잠긴다():
    ready, reason = formative_ready(_summary(10, 2))
    assert not ready
    assert "더 보시면" in reason  # 얼마나 더 해야 하는지까지 말해야 한다


def test_진도가_차면_열린다():
    ready, reason = formative_ready(_summary(10, 6))
    assert ready and reason == ""


def test_이해도가_낮아도_잠그지_않는다():
    # 못 하는 사람일수록 확인할 기회가 사라지면 안 된다.
    weak = ChapterMastery("1장", 10, 8, 0.1, ("모듈",))
    assert formative_ready(weak)[0]


def test_화면이_없으면_잠긴다():
    ready, reason = formative_ready(_summary(0, 0))
    assert not ready and reason


def test_잠금_기준이_진도와_일치한다():
    total = 10
    need = int(total * FORMATIVE_UNLOCK)
    assert formative_ready(_summary(total, need))[0]
    assert not formative_ready(_summary(total, need - 1))[0]


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
