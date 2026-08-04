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
    retrieval_gap,
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


def test_괄호_병기는_한쪽_표기만_써도_언급으로_친다():
    # 실측 사고: 개념명 "목 오브젝트 (Mock Object)"인데 본문은 "목 오브젝트"라고만
    # 써서, 넷 다 나와 있는 설명이 `언급 0/4`로 찍혔다. 토큰으로 쪼개면
    # "(Mock" "Object)"가 본문에 없어 70% 문턱을 못 넘는다.
    mock = [ConceptBrief("목 오브젝트 (Mock Object)", "대체 객체")]
    for body in (
        "목 오브젝트는 조건부 입력 시 계획된 행위를 수행하는 대체 객체다.",
        "Mock Object는 조건부 입력 시 계획된 행위를 수행한다.",
        "목 오브젝트 (Mock Object)는 대체 객체다.",
    ):
        covered, missing = coverage(parse_response(_raw(explanation=body), mock), mock)
        assert covered == 1, (body, missing)


def test_괄호가_이름의_일부면_떼지_않는다():
    # `Python input() 함수`의 괄호는 병기가 아니다. 떼면 원문과 안 맞는다.
    from app.features.curriculum.excerpt import aliases

    assert "Python input() 함수" in aliases("Python input() 함수")
    assert aliases("DRM(디지털 저작권 관리)")[1:] == ["DRM", "디지털 저작권 관리"]
    # 한 글자 주표기는 버린다 — "키"로 부분일치를 걸면 "키워드"까지 잡힌다.
    assert "키" not in aliases("키(Key)")


def test_토큰이_하나로_줄면_부분일치를_안_쓴다():
    # 오탐을 막다가 미탐이 생기는 지점. 2어절인데 한 어절이 1글자면 토큰 필터
    # (len>=2) 후 하나만 남아, 그 하나만 본문에 있어도 100%가 되어 통과한다.
    #   "제 1 정규형"              → ["정규형"]    → 제2·제3정규형까지 언급으로
    #   "목 오브젝트 (Mock Object)" → ["오브젝트"]  → 아무 오브젝트나 언급으로
    from app.features.curriculum.blocks import _mentions

    assert not _mentions("제 2 정규형은 부분 함수 종속을 제거한다.", "제 1 정규형")
    assert _mentions("제 1 정규형은 원자값만 갖는다.", "제 1 정규형")
    assert not _mentions("이 절은 오브젝트를 다룬다.", "목 오브젝트 (Mock Object)")
    assert _mentions("목 오브젝트는 대체 객체다.", "목 오브젝트 (Mock Object)")
    assert _mentions("Mock Object는 대체 객체다.", "목 오브젝트 (Mock Object)")


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


def test_원문을_앞에서_자르지_않고_개념_자리를_남긴다():
    """앞자르기는 뒤쪽 개념을 통째로 버린다.

    실측(표·헤딩을 지운 판 = 강의자료 흉내): 절이 자기 개념을 하나도 못 받는
    비율이 필기 22%·실기 29%였다. 조판 있는 실기 원본에서는 1%라 안 보였다.
    """
    from app.features.curriculum.blocks import MAX_SOURCE_CHARS, clip_around

    filler = "\n".join("관계 없는 줄입니다." * 3 for _ in range(300))
    source = (
        "XP의 핵심 가치는 다섯 가지다.\n"
        + filler
        + "\n애자일 개발 4가지 핵심 가치는 개인과 상호작용을 중시한다."
    )
    assert len(source) > MAX_SOURCE_CHARS * 3

    clipped = clip_around(source, CONCEPTS)
    # 앞자르기였다면 뒤쪽 개념이 사라진다 — 그게 이 함수가 막으려는 것이다.
    assert "애자일 개발 4가지 핵심 가치" not in source[:MAX_SOURCE_CHARS]
    for c in CONCEPTS:
        assert c.key in clipped, c.key
    assert len(clipped) <= MAX_SOURCE_CHARS
    assert "…" in clipped  # 건너뛴 자리를 표시해야 이어붙인 글임을 안다


def test_개념을_하나도_못_찾으면_앞에서_자른다():
    # 폴백이 있어야 원문이 통째로 프롬프트에 들어가는 사고를 막는다.
    from app.features.curriculum.blocks import MAX_SOURCE_CHARS, clip_around

    clipped = clip_around("나" * 5000, CONCEPTS)
    assert len(clipped) == MAX_SOURCE_CHARS


MCQ_OK = {
    "question": "시간 순서에 따른 메시지 교환을 표현하는 것은?",
    "options": ["XP의 핵심 가치", "애자일 개발 4가지 핵심 가치", "폭포수 모형", "나선형 모형"],
    "answer": "폭포수 모형",
    "explanation": "…",
}


def test_객관식이_블록으로_들어간다():
    blocks = parse_response(_raw(mcq=MCQ_OK), CONCEPTS)
    assert "mcq" in [b.type for b in blocks]


def test_정답이_보기에_없으면_버린다():
    bad = {**MCQ_OK, "answer": "보기에 없는 것"}
    assert "mcq" not in [b.type for b in parse_response(_raw(mcq=bad), CONCEPTS)]


def test_보기가_부족하면_버린다():
    bad = {**MCQ_OK, "options": ["하나", "둘"], "answer": "하나"}
    assert "mcq" not in [b.type for b in parse_response(_raw(mcq=bad), CONCEPTS)]


def test_보기에_중복이_있으면_버린다():
    bad = {**MCQ_OK, "options": ["A", "A", "B", "C"], "answer": "A"}
    assert "mcq" not in [b.type for b in parse_response(_raw(mcq=bad), CONCEPTS)]


def test_이_절과_무관한_정답은_버린다():
    """예시를 구체적으로 바꿨더니 모델이 그걸 그대로 베끼기 시작했다.

    실측: `접근 통제 기술` 절(DAC·MAC·RBAC)에 스키마 예시가 그대로 나왔다 —
    "이전 단계로 돌아갈 수 없는 고전적 생명주기 모형을 ____ 이라 한다"(답: 폭포수 모형).
    placeholder보다 나쁘다. 멀쩡해 보여서 형식 검사를 통과한다.
    """
    src = "XP는 애자일 방법론이다. 애자일 개발은 짧은 주기를 반복한다."
    baddie = [
        {
            "sentence": "이전 단계로 돌아갈 수 없는 고전적 생명주기 모형을 ____ 이라 한다.",
            "answer": "폭포수 모형",
        }
    ]
    blocks = parse_response(_raw(cloze=baddie), CONCEPTS, src)
    assert not any(b.type == "cloze" for b in blocks)

    # 이 절의 개념이면 통과한다.
    good = [{"sentence": "다섯 가지로 이루어진 것은 ____ 이다.", "answer": "XP의 핵심 가치"}]
    assert any(b.type == "cloze" for b in parse_response(_raw(cloze=good), CONCEPTS, src))

    # 원문에 있는 말도 통과한다(개념명이 아니어도 교재의 말이다).
    from_src = [{"sentence": "짧은 주기를 반복하는 것은 ____ 이다.", "answer": "애자일 개발"}]
    assert any(
        b.type == "cloze" for b in parse_response(_raw(cloze=from_src), CONCEPTS, src)
    )

    # 원문을 안 주면 검사하지 않는다 — 근거가 없다고 멀쩡한 문항까지 버리면 손해다.
    assert any(b.type == "cloze" for b in parse_response(_raw(cloze=baddie), CONCEPTS))


def test_스키마_예시를_베낀_객관식은_버린다():
    # 실측 사고: 모델이 스키마의 "다음 설명에 해당하는 것은?"을 그대로 쓰고
    # 정작 설명은 안 넣었다. 보기만 보고는 답을 고를 수 없는 문항이 된다.
    bad = {**MCQ_OK, "question": "다음 설명에 해당하는 것은?"}
    assert "mcq" not in [b.type for b in parse_response(_raw(mcq=bad), CONCEPTS)]


def test_객관식이_없어도_나머지는_살린다():
    blocks = parse_response(_raw(), CONCEPTS)  # mcq 필드 자체가 없음
    assert [b.type for b in blocks] == ["concept", "analogy", "cloze"]


def test_인출_누락을_잡는다():
    # 설명에 언급만 되고 한 번도 안 꺼낸 개념은 안다/모른다를 판정할 수 없다.
    blocks = parse_response(_raw(), CONCEPTS)  # cloze가 XP 하나뿐
    assert retrieval_gap(blocks, CONCEPTS) == ["애자일 개발 4가지 핵심 가치"]


def test_개념마다_빈칸이_있으면_누락이_없다():
    both = [
        {"sentence": "XP의 다섯 가치 중 하나는 ____ 이다.", "answer": "존중",
         "concept": "XP의 핵심 가치"},
        {"sentence": "개인과 상호작용을 중시하는 것은 ____ 이다.", "answer": "애자일",
         "concept": "애자일 개발 4가지 핵심 가치"},
    ]
    blocks = parse_response(_raw(cloze=both), CONCEPTS)
    assert retrieval_gap(blocks, CONCEPTS) == []


def test_프롬프트가_개념_수만큼_빈칸을_요구한다():
    p = build_prompt("절", CONCEPTS, "", "")
    assert f"빈칸 {len(CONCEPTS)}개" in p
    assert "객관식 1개" in p


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
