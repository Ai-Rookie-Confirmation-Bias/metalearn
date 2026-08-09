"""학습 상태·커리큘럼 배분 테스트.

여기가 틀리면 커리큘럼이 엉뚱하게 바뀐다. 그리고 그건 화면에 이유까지 적혀
나가므로 사용자가 바로 알아챈다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.curriculum.mastery import (  # noqa: E402
    DAY,
    DIAGNOSTIC,
    FORMATIVE,
    LEARNING,
    RETRIEVAL,
    REVIEW,
    SOLID_S,
    UNTOUCHED,
    WEAK,
    SectionMastery,
    chapter_summary,
    course_summary,
    record,
)
from app.features.curriculum.planner import (  # noqa: E402
    COMPRESSED,
    DEEP,
    NORMAL,
    mode_block,
    plan_chapter,
    plan_course,
)


NOW = 1_760_000_000.0  # 시계를 고정한다 — 망각 테스트가 실행 시각에 흔들리면 안 된다


def _run(
    section_id: str,
    results: list[bool],
    concept: str | None = None,
    kind: str = RETRIEVAL,
    at: float = NOW,
):
    s = SectionMastery(section_id)
    for r in results:
        s = record(s, r, concept, kind, at)
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


# ── 네 출처의 누적 ─────────────────────────────────────────────────


def test_출처마다_무게가_다르다():
    # 진단 오답은 "아직 안 배운 것"이지 무지의 증거가 아니다. 복습 정답은
    # 시간이 지나고도 꺼낸 것이라 방금 읽고 맞힌 것보다 센 증거다.
    assert _run("s", [True], kind=DIAGNOSTIC).weight == 0.5
    assert _run("s", [True], kind=RETRIEVAL).weight == 1.0
    assert _run("s", [True], kind=REVIEW).weight == 1.5
    assert _run("s", [True], kind=FORMATIVE).weight == 2.0


def test_진단_오답은_인출_정답에_금방_덮인다():
    # 배우기 전 틀린 것이 영원히 발목을 잡으면 "나아졌다"를 못 보여준다.
    s = SectionMastery("s")
    s = record(s, False, None, DIAGNOSTIC, NOW)  # 진단에서 틀림
    s = record(s, True, None, RETRIEVAL, NOW)  # 배우고 맞힘
    s = record(s, True, None, RETRIEVAL, NOW)
    s = record(s, True, None, RETRIEVAL, NOW)
    assert s.ratio >= 0.8, s.ratio  # 같은 무게였다면 0.75로 못 넘는다
    assert s.status == SOLID_S


def test_네_출처가_한_값으로_쌓인다():
    s = SectionMastery("s")
    s = record(s, True, None, DIAGNOSTIC, NOW)
    s = record(s, True, None, RETRIEVAL, NOW)
    s = record(s, True, None, REVIEW, NOW)
    s = record(s, True, None, FORMATIVE, NOW)
    assert s.attempts == 4
    assert s.weight == 5.0 and s.score == 5.0
    assert s.by_kind == {DIAGNOSTIC: 1, RETRIEVAL: 1, REVIEW: 1, FORMATIVE: 1}


def test_판정_자격은_가중으로_본다():
    # 진단만 2문제(1.0)로는 판정 못 한다. 인출 3문제(3.0)면 한다.
    assert _run("s", [True, True], kind=DIAGNOSTIC).status == LEARNING
    assert _run("s", [True, True, True], kind=RETRIEVAL).status == SOLID_S
    # 형성 2문제(4.0)면 그것만으로 충분하다
    assert _run("s", [True, True], kind=FORMATIVE).status == SOLID_S


# ── 망각곡선 ───────────────────────────────────────────────────────


def test_안_풀었으면_회상_강도가_0():
    assert SectionMastery("s").recall(NOW) == 0.0


def test_틀리기만_했으면_회상_강도가_0():
    # 못 꺼냈는데 "방금 꺼냈다"로 치면 복습이 안 돌아온다.
    assert _run("s", [False, False]).recall(NOW) == 0.0


def test_시간이_지나면_회상_강도가_떨어진다():
    s = _run("s", [True])
    assert s.recall(NOW) == 1.0
    assert s.recall(NOW + 30 * DAY) < 0.2


def test_망각은_이해도를_깎지_않는다():
    # 가만히 있는데 이해도가 내려가면 화면에서 설명할 수 없다.
    # 3연속 정답이면 반감기가 17.5일이라 30일 뒤 0.3 언저리다(실측).
    s = _run("s", [True, True, True])
    assert s.ratio == 1.0
    assert s.recall(NOW + 30 * DAY) < 0.5
    assert s.ratio == 1.0  # 그대로다


def test_연속으로_맞히면_오래_간다():
    # 한 번 맞힌 것과 세 번 연속 맞힌 것을 같은 속도로 잊는다고 보면
    # 복습이 끝없이 돌아온다.
    once = _run("s", [True])
    thrice = _run("s", [True, True, True])
    assert thrice.half_life > once.half_life
    later = NOW + 7 * DAY
    assert thrice.recall(later) > once.recall(later)


def test_틀리면_연속이_끊긴다():
    s = _run("s", [True, True, True, False])
    assert s.streak == 0


def test_잊혀가는_절이_복습_대상():
    # 이해도가 낮은 절이 아니라 잊혀가는 절이다.
    s = _run("s", [True, True, True])
    assert not s.needs_review(NOW)
    assert s.needs_review(NOW + 30 * DAY)


def test_한_번도_못_맞힌_절은_복습이_아니다():
    # 실측 사고: 형성평가 오답 1건뿐인 절이 "복습 대기"로 잡혔다.
    # 그건 아직 모르는 것이라 처방이 다르다 — 설명부터 다시 봐야 한다.
    s = _run("s", [False], kind=FORMATIVE)
    assert not s.needs_review(NOW)
    assert s.status in (LEARNING, WEAK)  # 이쪽이 잡는다


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


def test_목차도_출처별로_센다():
    states = [
        _run("s1", [True], kind=DIAGNOSTIC),
        _run("s2", [True, True], kind=RETRIEVAL),
    ]
    c = chapter_summary("1장", states, NOW)
    assert c.by_kind == {DIAGNOSTIC: 1, RETRIEVAL: 2}
    assert c.attempts == 3 and c.weight == 2.5


def test_보충_화면은_진도_분모에_안_들어간다():
    # 분모에 넣으면 보충을 끼울수록 진도가 뒤로 가고, 열려 있던 단원 평가가
    # 다시 잠긴다. 학습을 했는데 벌을 받는 그림이라 절대 안 된다.
    states = [_run("s1", [True]), _run("s2", [True]), SectionMastery("s3")]
    before = chapter_summary("1장", states)

    states.append(_run("x1", [True]))  # 보충 화면이 끼어들었다
    after = chapter_summary("1장", states, extra_ids=frozenset({"x1"}))

    assert after.sections_total == before.sections_total == 3
    assert after.progress == before.progress
    assert after.sections_extra == 1 and after.sections_extra_touched == 1


def test_보충_화면에서_푼_것도_실력이다():
    # 진도만 원문 기준이다. 이해도·복습은 보충도 똑같이 센다 —
    # 거기서 맞힌 것도 실력이고, 잊는 것도 마찬가지다.
    states = [_run("s1", [False, False]), _run("x1", [True, True, True])]
    c = chapter_summary("1장", states, extra_ids=frozenset({"x1"}))
    assert c.attempts == 5
    assert c.ratio > 0.5, c.ratio  # 보충에서 맞힌 게 반영된다


def test_목차가_복습_대상_절을_센다():
    states = [_run("s1", [True]), _run("s2", [True]), SectionMastery("s3")]
    assert chapter_summary("1장", states, NOW).sections_due == 0
    assert chapter_summary("1장", states, NOW + 30 * DAY).sections_due == 2


# ── 과목 전체: 하나의 누적값 ────────────────────────────────────────


def test_준비도는_이해도_진도_회상을_곱한다():
    # 하나라도 0이면 준비된 게 아니다.
    states = [_run(f"s{i}", [True, True, True]) for i in range(4)]
    course = course_summary([chapter_summary("1장", states, NOW)])
    assert course.readiness == 1.0

    # 절반만 봤으면 이해도가 만점이어도 준비는 절반
    half = states[:2] + [SectionMastery("s2"), SectionMastery("s3")]
    course = course_summary([chapter_summary("1장", half, NOW)])
    assert 0.4 < course.readiness < 0.6, course.readiness


def test_잊으면_준비도만_떨어지고_이해도는_남는다():
    # 준비도가 낮은 게 "잊은 것"인지 "아직 모르는 것"인지 갈라야 처방이 나온다.
    states = [_run(f"s{i}", [True, True, True]) for i in range(4)]
    ch = chapter_summary("1장", states, NOW + 30 * DAY)
    course = course_summary([ch])
    assert course.understanding == 1.0  # 이해는 그대로
    assert course.readiness < 0.5  # 지금 꺼내지진 않는다 — 절반 밑으로
    assert course.sections_due == 4  # 전부 복습 대상


def test_출처별_문항_수가_전체로_모인다():
    a = chapter_summary("1장", [_run("s1", [True], kind=DIAGNOSTIC)], NOW)
    b = chapter_summary("2장", [_run("s2", [True, True], kind=REVIEW)], NOW)
    assert course_summary([a, b]).by_kind == {DIAGNOSTIC: 1, REVIEW: 2}


# ── 배분 ───────────────────────────────────────────────────────────


def test_약하면_절을_늘린다():
    states = [_run(f"s{i}", [False, False, True]) for i in range(8)]
    plan = plan_chapter(2, chapter_summary("3장", states))
    assert plan.mode == DEEP
    assert plan.sections_planned > plan.sections_total
    assert "낮아" in plan.reason


def test_mode_block은_deep과_compressed만_지시를_낸다():
    # 배지와 설명 지시가 같은 규칙에서 나와야 한다.
    assert "늘림" in mode_block(DEEP)
    assert "핵심만" in mode_block(COMPRESSED)
    assert mode_block(NORMAL) == ""


def test_진단_목표가_안_배운_목차의_출발점을_정한다():
    empty = chapter_summary("1장", [SectionMastery(section_id=f"s{i}") for i in range(6)])

    urgent = plan_chapter(0, empty, goal="exam", deadline_weeks=2)
    assert urgent.mode == COMPRESSED
    assert "2주" in urgent.reason

    work = plan_chapter(0, empty, goal="work")
    assert work.mode == DEEP

    # 기한이 넉넉한 시험은 표준이다 — 범위를 빠뜨리는 쪽이 더 위험하다.
    assert plan_chapter(0, empty, goal="exam", deadline_weeks=12).mode == NORMAL
    assert plan_chapter(0, empty).mode == NORMAL


def test_목표로_정한_분량은_measured가_아니다():
    """★ 이 플래그 하나로 설명 형식이 남거나 사라진다(`mode_block`).

    선언은 "무엇을 하려는가"고 측정은 "지금 어떤가"다. 둘을 같은 값으로
    취급하면, 아무것도 재지 않은 목차에서 "이미 아는 사람에게 비유는 소음"
    이라는 근거로 학습자가 **직접 고른** 형식을 덮게 된다.
    """
    empty = chapter_summary("1장", [SectionMastery(section_id=f"s{i}") for i in range(6)])
    assert plan_chapter(0, empty, goal="exam", deadline_weeks=2).measured is False

    # 재서 나온 압축은 measured다 — 여기서는 성향을 덮어도 된다.
    solid = chapter_summary("1장", [_run(f"s{i}", [True, True, True]) for i in range(8)])
    measured_plan = plan_chapter(0, solid, goal="exam", deadline_weeks=2)
    assert measured_plan.mode == COMPRESSED
    assert measured_plan.measured is True
    assert "이해도" in measured_plan.reason  # 목표가 아니라 측정이 말한다


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
