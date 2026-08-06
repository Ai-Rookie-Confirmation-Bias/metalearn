"""인출 라벨 검증 — 오측정이 미측정보다 나쁘다."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.curriculum.blocks import Block, ConceptBrief, retrieval_gap  # noqa: E402
from app.features.curriculum.retrieval_label import (  # noqa: E402
    is_name_recall,
    scrub_blocks,
    scrub_cloze,
)

CONCEPTS = [
    ConceptBrief("애자일 모형", "반복적으로 개발하며 변화에 대응한다"),
    ConceptBrief("프로토타입 모형", "견본을 만들어 요구를 확인한다"),
]


def _cloze(answer: str, concept: str, kind: str = "상황") -> Block:
    return Block(
        "cloze",
        {"sentence": f"그런 방식은 ____ 이다.", "answer": answer, "kind": kind},
        concept_keys=(concept,),
    )


def test_다른_화면_개념이_정답이면_폐기():
    # 실측: concept='애자일 모형' answer='XP...' — 이 화면에 없는 개념
    bad = _cloze("XP(eXtreme Programming)", "애자일 모형", "상황")
    assert scrub_cloze(bad, CONCEPTS, foreign_keys=("XP(eXtreme Programming)",)) is None


def test_같은_화면_다른_개념이_정답이면_폐기():
    bad = _cloze("프로토타입 모형", "애자일 모형", "상황")
    assert scrub_cloze(bad, CONCEPTS) is None


def test_이름_인출은_개념키를_고정한다():
    ok = scrub_cloze(_cloze("애자일 모형", "애자일 모형", "상황"), CONCEPTS)
    assert ok is not None
    assert ok.concept_keys == ("애자일 모형",)
    assert is_name_recall(ok, CONCEPTS)


def test_성질은_살리고_숙련도키를_비운다():
    # 실측: concept='프로토타입 모형' answer='견본·시제품'
    prop = scrub_cloze(_cloze("견본·시제품", "프로토타입 모형", "성질"), CONCEPTS)
    assert prop is not None
    assert prop.concept_keys == ()
    assert not is_name_recall(prop, CONCEPTS)


def test_정의라고_신고했는데_답이_개념명이_아니면_폐기():
    fake = _cloze("견본·시제품", "프로토타입 모형", "정의")
    assert scrub_cloze(fake, CONCEPTS) is None


def test_성질만_있으면_누락이다():
    blocks = scrub_blocks(
        [_cloze("견본·시제품", "프로토타입 모형", "성질")],
        CONCEPTS,
    )
    assert retrieval_gap(blocks, CONCEPTS) == ["애자일 모형", "프로토타입 모형"]


def test_남의_개념명을_품었다고_폐기하지_않는다():
    # 실측 사고: 성질 정답이 문서 어딘가의 개념 '상태'를 품었다는 이유로 죽었다.
    # foreign은 문서 전체(371개)가 상대라 포함 매칭을 쓰면 멀쩡한 문항이 사라진다.
    long_answer = "이미 오름차순으로 정렬된 상태를 유지하는 배열의 일부"
    kept = scrub_cloze(
        _cloze(long_answer, "애자일 모형", "성질"),
        CONCEPTS,
        foreign_keys=("상태", "배열"),
    )
    assert kept is not None
    assert kept.concept_keys == ()


def test_성질은_라벨을_content에_남긴다():
    # concept_keys를 비우는 건 숙련도 오귀속을 막기 위해서다. 정의문 대조(L1 게이트)는
    # 계속 해야 하므로 어느 개념 문장이었는지는 남아야 한다.
    prop = scrub_cloze(_cloze("견본·시제품", "프로토타입 모형", "성질"), CONCEPTS)
    assert prop is not None
    assert prop.content["concept"] == "프로토타입 모형"


def test_이름_인출이_있으면_그_개념은_누락이_아니다():
    blocks = scrub_blocks(
        [
            _cloze("애자일 모형", "애자일 모형", "상황"),
            _cloze("견본·시제품", "프로토타입 모형", "성질"),
        ],
        CONCEPTS,
    )
    assert retrieval_gap(blocks, CONCEPTS) == ["프로토타입 모형"]
