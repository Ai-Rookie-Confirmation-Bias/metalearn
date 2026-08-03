"""학습 블록 프롬프트·파싱 단위 테스트.

실측에서 나온 사고를 회귀 대상으로 잡는다:
  ① 모델이 스키마 placeholder를 그대로 베껴 빈칸 문항을 만들었다
  ② 커버리지를 정확 일치로 세다가 정상 문장을 누락으로 판정했다
  ③ analogy에 문자열 "null"이 들어왔다
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.curriculum.blocks import (  # noqa: E402
    ConceptBrief,
    build_prompt,
    coverage,
    parse_response,
)

CONCEPTS = [
    ConceptBrief("XP의 핵심 가치", "XP의 5가지 핵심 가치"),
    ConceptBrief("애자일 개발 4가지 핵심 가치", "개인·실행·협업·변화 대응"),
]


def _raw(**over) -> str:
    import json

    body = {
        "explanation": "애자일 개발 4가지 핵심 가치는 …이고, XP의 핵심 가치는 …이다.",
        "analogy": "요리사가 손님 반응을 보며 맛을 조절하는 것과 같다.",
        "cloze": [
            {
                "sentence": "XP의 핵심 가치 중 ____ 은 팀원 간 신뢰를 뜻한다.",
                "answer": "존중",
                "concept": "XP의 핵심 가치",
            }
        ],
    }
    body.update(over)
    return json.dumps(body, ensure_ascii=False)


def test_정상_응답이_블록으로_변환된다():
    blocks = parse_response(_raw(), CONCEPTS)
    types = [b.type for b in blocks]
    assert types == ["concept", "analogy", "cloze"], types


def test_analogy가_문자열_null이면_버린다():
    # 실측: 모델이 JSON null 대신 문자열 "null"을 넣었다.
    for bad in ("null", "None", "N/A", "  "):
        blocks = parse_response(_raw(analogy=bad), CONCEPTS)
        assert not any(b.type == "analogy" for b in blocks), bad


def test_스키마_예시를_베낀_빈칸은_버린다():
    # 실측 사고: "____ 가 들어갈 자리를 포함한 문장"이 그대로 나왔다.
    bad = [{"sentence": "____ 가 들어갈 자리를 포함한 문장", "answer": "의사소통"}]
    blocks = parse_response(_raw(cloze=bad), CONCEPTS)
    assert not any(b.type == "cloze" for b in blocks)


def test_정답이_문장에_남아있으면_버린다():
    bad = [{"sentence": "XP의 존중은 ____ 을 뜻한다.", "answer": "존중"}]
    blocks = parse_response(_raw(cloze=bad), CONCEPTS)
    assert not any(b.type == "cloze" for b in blocks)


def test_빈칸_표시가_없으면_버린다():
    bad = [{"sentence": "XP의 핵심 가치는 다섯 가지다.", "answer": "존중"}]
    assert not any(b.type == "cloze" for b in parse_response(_raw(cloze=bad), CONCEPTS))


def test_문맥이_너무_짧으면_버린다():
    bad = [{"sentence": "____ 이다.", "answer": "존중"}]
    assert not any(b.type == "cloze" for b in parse_response(_raw(cloze=bad), CONCEPTS))


def test_설명이_깨져도_나머지는_살린다():
    # 부가 항목 하나 때문에 본체를 잃으면 안 된다 — 반대로 본체가 없어도 나머지는 남긴다.
    blocks = parse_response(_raw(explanation=""), CONCEPTS)
    assert [b.type for b in blocks] == ["analogy", "cloze"]


def test_JSON이_깨지면_빈_목록():
    assert parse_response("완전히 깨진 응답", CONCEPTS) == []


def test_커버리지가_표기_차이를_흡수한다():
    # 실측 사고: 본문이 "XP(eXtreme Programming)의 핵심 가치"로 써서 누락 판정됐다.
    blocks = parse_response(
        _raw(
            explanation=(
                "XP(eXtreme Programming)의 핵심 가치는 다섯 가지다. "
                "애자일 개발 자체의 4가지 핵심 가치는 개인과 상호작용을 중시한다."
            )
        ),
        CONCEPTS,
    )
    covered, missing = coverage(blocks, CONCEPTS)
    assert covered == 2, missing


def test_진짜_누락은_잡는다():
    blocks = parse_response(
        _raw(explanation="애자일 개발 4가지 핵심 가치만 설명한다.", analogy="null", cloze=[]),
        CONCEPTS,
    )
    covered, missing = coverage(blocks, CONCEPTS)
    assert covered == 1 and missing == ["XP의 핵심 가치"], (covered, missing)


def test_프롬프트에_개념이_모두_들어간다():
    p = build_prompt("애자일 개발", CONCEPTS, "", "")
    for c in CONCEPTS:
        assert c.key in p and c.definition in p


def test_성향_지시가_없으면_프롬프트에_안_들어간다():
    plain = build_prompt("애자일 개발", CONCEPTS, "", "")
    tuned = build_prompt("애자일 개발", CONCEPTS, "[이 학습자에게 맞춘 설명 방식]\n- 비유 먼저", "")
    assert "맞춘 설명 방식" not in plain
    assert "맞춘 설명 방식" in tuned


def test_원문이_길면_잘라서_붙인다():
    long_src = "가" * 5000
    p = build_prompt("절", CONCEPTS, "", long_src)
    assert "교재 원문" in p
    assert p.count("가") < 2000


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
