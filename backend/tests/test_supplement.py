"""보충 화면 삽입 — 반복해서 틀린 선수 개념을 그 앞에 끼운다.

여기가 틀리면 두 가지가 무너진다. 목차가 보충으로 뒤덮이거나(진도가 안 나감),
새로고침할 때마다 화면이 생겼다 사라지거나(자기가 뭘 보는지 모름).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.curriculum.grouping import Concept, Section  # noqa: E402
from app.features.curriculum.planner import (  # noqa: E402
    INSERT_AFTER_WRONG,
    MAX_INSERT_PER_CHAPTER,
    supplement_sections,
)

# 응집도 ← 결합도 ← 모듈화 순으로 선수 관계가 걸려 있다.
POOL = {
    "모듈화": Concept("모듈화", "시스템을 기능 단위로 나누는 것"),
    "결합도": Concept("결합도", "모듈 사이의 관련 정도", prerequisites=("모듈화",)),
    "응집도": Concept("응집도", "모듈 내부 요소의 관련 정도", prerequisites=("결합도",)),
    "팬인": Concept("팬인", "자신을 호출하는 상위 모듈 수", prerequisites=("모듈화",)),
}


def _sec(title: str, keys: list[str]) -> Section:
    return Section(
        title=title,
        concepts=tuple(POOL[k] for k in keys),
        reason="",
        section_id=f"s::{title}",
    )


def test_반복해서_틀린_선수는_그_화면_앞에_끼운다():
    sections = [_sec("응집도 화면", ["응집도"])]
    out = supplement_sections(sections, {"결합도": INSERT_AFTER_WRONG}, POOL)

    assert [s.title for s in out] == ["결합도 다시 보기", "응집도 화면"]
    assert out[0].inserted and not out[1].inserted
    assert out[0].concept_keys == ("결합도",)


def test_한두_번_틀린_것으로는_화면을_안_만든다():
    # 실수 한 번이 진도를 막으면 안 된다. 그건 설명 안 tie_in이 짚는다.
    sections = [_sec("응집도 화면", ["응집도"])]
    out = supplement_sections(sections, {"결합도": INSERT_AFTER_WRONG - 1}, POOL)
    assert [s.title for s in out] == ["응집도 화면"]


def test_이_화면에_이미_있는_개념은_안_끼운다():
    # 지금 배우는 걸 "앞에서 틀렸다"고 따로 떼어 보여주는 건 이상하다.
    sections = [_sec("결합도와 응집도", ["결합도", "응집도"])]
    out = supplement_sections(sections, {"결합도": 9}, POOL)
    assert len(out) == 1


def test_같은_개념으로_두_번_끼우지_않는다():
    sections = [_sec("A", ["결합도"]), _sec("B", ["팬인"])]
    out = supplement_sections(sections, {"모듈화": 9}, POOL)
    assert [s.title for s in out] == ["모듈화 다시 보기", "A", "B"]


def test_목차_하나에_상한이_있다():
    # 보충이 본 내용을 덮으면 그건 보강이 아니라 다른 커리큘럼이다.
    pool = dict(POOL)
    sections = []
    for i in range(5):
        prereq, target = f"선수{i}", f"대상{i}"
        pool[prereq] = Concept(prereq, f"정의 {i}")
        pool[target] = Concept(target, "", prerequisites=(prereq,))
        sections.append(
            Section(title=target, concepts=(pool[target],), reason="", section_id=target)
        )

    out = supplement_sections(sections, {f"선수{i}": 9 for i in range(5)}, pool)

    assert sum(1 for s in out if s.inserted) == MAX_INSERT_PER_CHAPTER
    assert sum(1 for s in out if not s.inserted) == 5  # 원래 화면은 하나도 안 잃는다


def test_같은_상태면_같은_결과다():
    # 새로고침할 때마다 보충이 생겼다 사라지면 학습자는 뭘 보는지 알 수 없다.
    sections = [_sec("응집도 화면", ["응집도"])]
    a = supplement_sections(sections, {"결합도": 9}, POOL)
    b = supplement_sections(sections, {"결합도": 9}, POOL)
    assert [s.section_id for s in a] == [s.section_id for s in b]
    assert a[0].section_id == "supp::결합도"  # 진도 기록이 붙을 자리


def test_왜_여기_있는지_화면에_적힌다():
    # 이유가 없으면 교재에 원래 있던 내용이라고 오해한다.
    out = supplement_sections([_sec("응집도 화면", ["응집도"])], {"결합도": 4}, POOL)
    assert "결합도" in out[0].reason
    assert "4번" in out[0].reason
    assert "응집도 화면" in out[0].reason


def test_보충_화면도_원문_대신_쓸_글이_있다():
    # source가 비면 설명 에이전트가 근거 없이 쓴다. 정의문이라도 넘긴다.
    out = supplement_sections([_sec("응집도 화면", ["응집도"])], {"결합도": 9}, POOL)
    assert POOL["결합도"].definition in out[0].source


def test_순서는_다시_매겨진다():
    sections = [_sec("A", ["결합도"]), _sec("B", ["응집도"])]
    out = supplement_sections(sections, {"모듈화": 9}, POOL)
    assert [s.order for s in out] == list(range(len(out)))
