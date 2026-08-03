"""학습 상태·커리큘럼 배분 테스트.

여기가 틀리면 커리큘럼이 엉뚱하게 바뀐다. 그리고 그건 화면에 이유까지 적혀
나가므로 사용자가 바로 알아챈다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.curriculum.mastery import (  # noqa: E402
    LEARNING,
    SOLID_S,
    UNTOUCHED,
    WEAK,
    SectionMastery,
    chapter_summary,
    record,
)
from app.features.curriculum.planner import (  # noqa: E402
    COMPRESSED,
    DEEP,
    NORMAL,
    plan_chapter,
    plan_course,
)


def _run(section_id: str, results: list[bool], concept: str | None = None):
    s = SectionMastery(section_id)
    for r in results:
        s = record(s, r, concept)
    return s


# ── 절 상태 ────────────────────────────────────────────────────────


def test_안_풀면_미학습():
    s = SectionMastery("s1")
    assert s.status == UNTOUCHED and s.ratio == 0.0


def test_적게_풀면_판정을_보류한다():
    # 1문제 맞혔다고 "확실히 안다"고 하면 안 된다.
    for results in ([True], [True, True]):
        assert _run("s1", results).status == LEARNING, results


def test_충분히_풀면_판정한다():
    assert _run("s1", [True, True, True]).status == SOLID_S
    assert _run("s1", [False, False, False]).status == WEAK


def test_틀린_개념을_센다():
    s = _run("s1", [False, False, True], concept="순차 다이어그램")
    assert s.wrong_by_concept == {"순차 다이어그램": 2}
    assert s.weak_concepts == ("순차 다이어그램",)


def test_한_번_틀린_건_약점이_아니다():
    # 실수일 수 있다.
    s = _run("s1", [False, True, True], concept="UML")
    assert s.weak_concepts == ()


def test_정답이면_개념을_안_센다():
    s = _run("s1", [True, True, True], concept="UML")
    assert s.wrong_by_concept == {}


def test_최근에_나아지면_표시한다():
    # 처음엔 틀리다 나중에 맞히면 배운 것이다. 누적 정답률만 보면 안 보인다.
    s = _run("s1", [False, False, False, True, True, True])
    assert s.ratio < 0.8 and s.improving


def test_이미_잘하면_나아짐_표시_안_한다():
    assert not _run("s1", [True, True, True, True]).improving


def test_최근_기록은_창_크기만큼만_남는다():
    s = _run("s1", [True] * 20)
    assert len(s.recent) == 5


def test_기록은_원본을_바꾸지_않는다():
    a = SectionMastery("s1")
    b = record(a, True)
    assert a.attempts == 0 and b.attempts == 1


# ── 목차 집계 ──────────────────────────────────────────────────────


def test_안_푼_절은_이해도에서_뺀다():
    # 안 푼 절을 0점으로 세면 진도가 곧 이해도가 되어 버린다.
    states = [_run("s1", [True, True, True]), SectionMastery("s2"), SectionMastery("s3")]
    c = chapter_summary("1장", states)
    assert c.ratio == 1.0, c.ratio
    assert c.progress < 0.4  # 진도는 따로 낮게 나온다


def test_시도_횟수로_가중한다():
    # 3문제 푼 절과 10문제 푼 절을 같은 무게로 평균내면 안 된다.
    states = [_run("s1", [True] * 9 + [False]), _run("s2", [False, False])]
    c = chapter_summary("1장", states)
    assert 0.7 < c.ratio < 0.8, c.ratio  # 단순 평균이면 0.45


def test_절을_넘나드는_약점을_모은다():
    states = [
        _run("s1", [False], concept="캐시"),
        _run("s2", [False], concept="캐시"),
    ]
    assert chapter_summary("1장", states).weak_concepts == ("캐시",)


# ── 배분 ───────────────────────────────────────────────────────────


def test_약하면_절을_늘린다():
    states = [_run(f"s{i}", [False, False, True]) for i in range(8)]
    plan = plan_chapter(2, chapter_summary("3장", states))
    assert plan.mode == DEEP
    assert plan.sections_planned > plan.sections_total
    assert "낮아" in plan.reason


def test_잘하면_압축하되_없애지_않는다():
    # "이미 아니까 건너뛰세요"는 개인화가 아니라 방치다.
    states = [_run(f"s{i}", [True, True, True]) for i in range(8)]
    plan = plan_chapter(0, chapter_summary("1장", states))
    assert plan.mode == COMPRESSED
    assert 0 < plan.sections_planned < plan.sections_total


def test_안_본_목차는_표준():
    plan = plan_chapter(3, chapter_summary("4장", [SectionMastery("s1")] * 5))
    assert plan.mode == NORMAL and not plan.changed


def test_앞_목차_약점이_다음_목차에_녹는다():
    # 새 단원을 만들지 않는다 — 지금 배우는 것과 엮어서 설명한다.
    plan = plan_chapter(
        3, chapter_summary("4장", [SectionMastery("s1")] * 6), ("세션 계층",)
    )
    assert plan.mode == DEEP
    assert "세션 계층" in plan.reason and "함께 녹입니다" in plan.reason
    assert "세션 계층" in plan.weak_concepts


def test_목차_순서는_절대_안_바뀐다():
    # 실측: 선수관계 96~99%가 목차 안에서 일어난다. 재배치할 근거가 없다.
    summaries = [
        chapter_summary(f"{i}장", [_run("s", [False] * 3 if i == 2 else [True] * 3)])
        for i in range(5)
    ]
    plans = plan_course(summaries)
    assert [p.chapter for p in plans] == [f"{i}장" for i in range(5)]
    assert [p.order for p in plans] == [0, 1, 2, 3, 4]
    # 3번째만 약한데도 순서는 그대로, 분량만 다르다
    assert plans[2].mode == DEEP


def test_모든_변경에_이유가_있다():
    for states, carry in (
        ([_run(f"s{i}", [False] * 3) for i in range(4)], ()),
        ([_run(f"s{i}", [True] * 3) for i in range(4)], ()),
        ([SectionMastery("s1")] * 4, ("캐시",)),
    ):
        plan = plan_chapter(0, chapter_summary("장", states), carry)
        if plan.changed:
            assert plan.reason, plan


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
