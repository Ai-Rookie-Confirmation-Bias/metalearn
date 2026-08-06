"""에이전트의 순수 부분 — 프롬프트가 무엇을 요구하는가, 결과를 어떻게 판정하는가.

LLM 호출은 안 한다. 여기서 잠그는 건 **시키는 내용**과 **인정하는 기준**이다.
둘 다 실측에서 한 번씩 무너진 자리라 테스트로 고정한다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.curriculum.agents.explanation import (  # noqa: E402
    TIE_IN_LABEL,
    build_prompt,
    tied_in,
)
from app.features.curriculum.agents.retrieval import (  # noqa: E402
    _levels_of,
    build_fill_prompt,
)
from app.features.curriculum.blocks import Block, ConceptBrief  # noqa: E402
from app.features.curriculum.retrieval_label import scrub_blocks  # noqa: E402
from app.features.curriculum.retrieval_level import L1_RECALL  # noqa: E402

CONCEPTS = [
    ConceptBrief("결합도", "모듈 사이의 관련 정도"),
    ConceptBrief("응집도", "모듈 내부 요소의 관련 정도"),
    ConceptBrief("팬인", "자신을 호출하는 상위 모듈 수"),
]


def _tie_block(text: str) -> Block:
    return Block("tie_in", {"text": text, "label": TIE_IN_LABEL}, concept_keys=())


# ── 보충 프롬프트: 빠진 것만 시킨다 ────────────────────────────────


def test_보충은_빠진_개념만_요구한다():
    # 개념 10개 중 2개가 빠졌을 때 10개를 다시 시키면 또 8개만 만든다(실측).
    p = build_fill_prompt("모듈", CONCEPTS, [CONCEPTS[2]], "설명 본문")
    assert "1개" in p
    assert "팬인" in p


def test_보충은_이미_있는_개념을_다시_만들지_말라고_한다():
    p = build_fill_prompt("모듈", CONCEPTS, [CONCEPTS[2]], "설명 본문")
    assert "결합도" in p and "응집도" in p  # 있다고 알려주되
    assert "다시 만들지 마라" in p  # 만들진 말라고


def test_보충_예시는_빠진_개념으로_완성돼_있다():
    # 추상 자리(`"…____…"`)를 주면 모델이 그대로 낸다 — 다섯 번 겪었다.
    p = build_fill_prompt("모듈", CONCEPTS, [CONCEPTS[2]], "설명")
    assert '"answer": "팬인"' in p and '"concept": "팬인"' in p


def test_보충은_이름_인출만_시킨다():
    # 누락 보충은 성질로 메우면 안 된다 — 숙련도에 쓸 이름 인출이 목적이다.
    p = build_fill_prompt("모듈", CONCEPTS, [CONCEPTS[2]], "설명")
    assert "상황 또는 정의" in p
    assert "성질 유형은 만들지 마라" in p


def test_라벨_검증_뒤에도_L1_게이트가_성질_문항을_잰다():
    # scrub이 성질 문항의 concept_keys를 비운다. 그때 정의문을 못 찾으면
    # `assess_cloze`가 "잴 수 없으면 L2"로 올려 **정의문을 통째로 베낀 문항이
    # 게이트를 통과한다.** 라벨은 content.concept에 남아야 한다.
    copied = Block(
        "cloze",
        {"sentence": "모듈 사이의 ____ 정도", "answer": "관련", "kind": "성질"},
        concept_keys=("결합도",),
    )
    assert _levels_of([copied], CONCEPTS, "") == [L1_RECALL]
    assert _levels_of(scrub_blocks([copied], CONCEPTS), CONCEPTS, "") == [L1_RECALL]


def test_전부_빠졌으면_전부_요구한다():
    p = build_fill_prompt("모듈", CONCEPTS, CONCEPTS, "설명")
    assert "3개" in p
    assert "다시 만들지 마라" not in p  # 이미 있는 게 없으니 그 말도 없다


# ── 약점 엮기: 요청이 아니라 결과를 본다 ──────────────────────────


def test_문단도_개념명도_있어야_인정한다():
    b = _tie_block("지난번에 결합도를 놓치셨는데, 응집도와 짝으로 보면 쉽습니다.")
    assert tied_in([b], ("결합도",)) == ("결합도",)


def test_문단이_없으면_인정_안_한다():
    # 모델이 "엮을 게 없다"고 판단해 null을 냈으면 화면 ⚡도 뜨면 안 된다.
    body = Block("concept", {"text": "결합도는 …"}, concept_keys=())
    assert tied_in([body], ("결합도",)) == ()


def test_개념명이_없으면_인정_안_한다():
    # 문단은 썼는데 이름을 안 쓰면 학습자가 "그때 그거"라고 못 알아본다.
    b = _tie_block("앞에서 배운 것과 이어지는 내용입니다.")
    assert tied_in([b], ("결합도",)) == ()


def test_요청한_것_중_들어간_것만_돌려준다():
    b = _tie_block("결합도를 다시 짚고 갑니다.")
    assert tied_in([b], ("결합도", "팬인")) == ("결합도",)


def test_약점을_요청_안_했으면_비어_있다():
    b = _tie_block("결합도를 다시 짚고 갑니다.")
    assert tied_in([b], ()) == ()


# ── 설명 프롬프트: 약점이 있을 때만 말한다 ────────────────────────


def test_약점이_없으면_아무_말도_안_한다():
    p = build_prompt("모듈", CONCEPTS)
    assert "tie_in" not in p
    assert "최근" not in p


def test_약점이_있으면_필드를_연다():
    # 본문 안에 넣으라고 하면 안 나온다(실측 0회). 별도 필드라야 나온다.
    p = build_prompt("모듈", CONCEPTS, weak_concepts=("팬아웃",))
    assert "tie_in" in p
    assert "팬아웃" in p
    # 엮으라고만 하면 무관한 절에도 갖다 붙인다. 빠져나갈 길을 같이 준다
    assert "억지로" in p and "null" in p


def test_분량_모드가_프롬프트에_붙는다():
    # plan.mode가 화면에만 뜨고 설명에 안 들어가면 거짓이다.
    plain = build_prompt("모듈", CONCEPTS)
    deep = build_prompt("모듈", CONCEPTS, mode_block="[이 단원의 분량 — 설명을 늘림]\n- 길게")
    assert "이 단원의 분량" not in plain
    assert "이 단원의 분량" in deep and "길게" in deep


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


def test_보충_예시가_스스로_필터를_통과한다():
    # ★ 예시가 곧 출력이다(일곱 번째). 예시가 '그런 상황에서 쓰는 것이 ____ 다.'였는데
    # 모델이 그대로 베껴 세 개념 전부 같은 문장을 냈고, 앞 문장을 가리키는 문장이라
    # 파서가 다 버려 0문항이 됐다. 예시는 **베끼면 오히려 맞는 모양**이어야 한다.
    p = build_fill_prompt("모듈", CONCEPTS, CONCEPTS, "설명")
    import json, re
    from app.features.curriculum.blocks import parse_response

    # 프롬프트 안의 예시를 그대로 응답인 척 넣어본다.
    examples = re.findall(r'\{"kind".*?\}', p)
    assert examples, "예시가 프롬프트에 없다"
    raw = json.dumps({"cloze": [json.loads(e) for e in examples]}, ensure_ascii=False)
    blocks = [b for b in parse_response(raw, CONCEPTS, "설명") if b.type == "cloze"]
    assert len(blocks) == len(CONCEPTS), f"예시를 베끼면 {len(blocks)}개만 남는다"
