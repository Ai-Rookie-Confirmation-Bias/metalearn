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


def test_분류어를_안_붙여도_정답으로_인정한다():
    """실측 사고: `폭포수`라고 적었는데 정답이 `폭포수 모형`이라 오답 처리됐다.

    개념을 정확히 꺼냈는데 분류어를 안 붙였다고 틀렸다고 하면 **인출이 아니라
    표기를 측정하는 것**이다.
    """
    from app.features.curriculum.blocks import accepted_answers

    # 분류어(`모형`)를 세 개 이상이 공유해야 분류어로 인정된다.
    models = [
        ConceptBrief("폭포수 모형", ""),
        ConceptBrief("나선형 모형", ""),
        ConceptBrief("애자일 모형", ""),
    ]
    got = accepted_answers("폭포수 모형", models)
    assert "폭포수 모형" in got and "폭포수" in got
    # 다른 개념까지 인정하면 안 된다.
    assert "나선형" not in got and "모형" not in got

    # 괄호 병기도 인정한다.
    ac = [ConceptBrief("강제 접근 통제 (MAC)", ""), ConceptBrief("임의 접근 통제 (DAC)", "")]
    got = accepted_answers("강제 접근 통제 (MAC)", ac)
    assert "MAC" in got and "강제 접근 통제" in got


def test_교재가_단_약어도_정답으로_인정한다():
    """`익스트림 프로그래밍`의 정답에 `XP`도 들어가야 한다(yoonhs 지적).

    교재는 `※ 익스트림 프로그래밍 (eXtreme Programming, XP)`처럼 약어를 괄호로
    다는데 파싱이 주는 개념명엔 안 들어 있다. 개념의 21~26%가 이 경우다.
    """
    from app.features.curriculum.blocks import accepted_answers

    xp = [ConceptBrief("익스트림 프로그래밍", "고객 참여와 신속한 개발"), ConceptBrief("피드백", "")]
    src = "# ※ 익스트림 프로그래밍 (eXtreme Programming, XP)\n- 고객의 요구사항에…"
    got = accepted_answers("익스트림 프로그래밍", xp, src)
    assert "XP" in got and "eXtreme Programming" in got

    # 괄호 안이 이름이 아니라 설명이면 별칭이 아니다.
    proto = [ConceptBrief("프로토타입", "")]
    desc = "프로토타입 (고객의 needs를 파악하기 위해 만드는 견본이다)"
    assert accepted_answers("프로토타입", proto, desc) == ["프로토타입"]


def test_다른_개념과_겹치는_형태는_인정하지_않는다():
    # `자료 결합도`를 `자료`로 인정했는데 절에 `자료 사전`이 있으면 둘을 못 가린다.
    from app.features.curriculum.blocks import accepted_answers

    coupling = [
        ConceptBrief("자료 결합도", ""),
        ConceptBrief("제어 결합도", ""),
        ConceptBrief("스탬프 결합도", ""),
        ConceptBrief("자료 사전", ""),
    ]
    got = accepted_answers("자료 결합도", coupling)
    assert "자료 결합도" in got
    assert "자료" not in got  # `자료 사전`과 헷갈린다


def test_객관식은_묻는_개념을_따로_싣는다():
    """실측 사고: 객관식 오답이 **항상 절의 첫 개념**에 기록됐다.

    concept_keys가 절 전체(구별 문항이라 맞다)인데 화면이 conceptKeys[0]을 썼다.
    객관식 5/5가 오귀속이었고, 그게 wrong_by_concept → weak_concepts → carry_over →
    다음 목차 설명으로 흘러 학습 루프의 입력을 오염시켰다.
    """
    blocks = parse_response(_raw(mcq=MCQ_OK), CONCEPTS)
    mcq = next(b for b in blocks if b.type == "mcq")
    # MCQ_OK의 정답은 "폭포수 모형" — 이 절 개념이 아니므로 None이어야 한다.
    assert mcq.content["concept"] is None

    on_topic = {**MCQ_OK, "answer": "XP의 핵심 가치"}
    mcq = next(
        b for b in parse_response(_raw(mcq=on_topic), CONCEPTS) if b.type == "mcq"
    )
    assert mcq.content["concept"] == "XP의 핵심 가치"
    # concept_keys는 절 전체 그대로 — 보기가 전부 이 절 개념이라 그게 맞다.
    assert len(mcq.concept_keys) == len(CONCEPTS)


def test_객관식이_없어도_나머지는_살린다():
    blocks = parse_response(_raw(), CONCEPTS)  # mcq 필드 자체가 없음
    assert [b.type for b in blocks] == ["concept", "analogy", "cloze"]


def test_인출_누락을_잡는다():
    # 기본 fixture cloze는 answer='존중'(성질)이라 이름 인출이 아니다.
    # 라벨만 세면 XP가 "물어본 것"으로 잡히지만, 오측정이므로 둘 다 누락이다.
    blocks = parse_response(_raw(), CONCEPTS)  # cloze가 XP 성질 하나뿐
    assert retrieval_gap(blocks, CONCEPTS) == [
        "XP의 핵심 가치",
        "애자일 개발 4가지 핵심 가치",
    ]


def test_개념마다_이름_인출이_있으면_누락이_없다():
    both = [
        {
            "sentence": "다섯 가지 핵심 가치를 강조하는 개발법은 ____ 이다.",
            "answer": "XP의 핵심 가치",
            "concept": "XP의 핵심 가치",
            "kind": "상황",
        },
        {
            "sentence": "개인과 상호작용을 중시하는 것은 ____ 이다.",
            "answer": "애자일 개발 4가지 핵심 가치",
            "concept": "애자일 개발 4가지 핵심 가치",
            "kind": "상황",
        },
    ]
    blocks = parse_response(_raw(cloze=both), CONCEPTS)
    assert retrieval_gap(blocks, CONCEPTS) == []


def test_성질_빈칸만으로는_누락을_못_메운다():
    # answer가 개념명이 아니면 라벨이 있어도 이름 인출이 아니다.
    prop = [
        {
            "sentence": "XP의 핵심 가치 중 ____ 은 팀원 간 신뢰를 뜻한다.",
            "answer": "존중",
            "concept": "XP의 핵심 가치",
            "kind": "성질",
        },
        {
            "sentence": "개인과 상호작용을 중시하는 것은 ____ 이다.",
            "answer": "애자일 개발 4가지 핵심 가치",
            "concept": "애자일 개발 4가지 핵심 가치",
            "kind": "상황",
        },
    ]
    blocks = parse_response(_raw(cloze=prop), CONCEPTS)
    assert retrieval_gap(blocks, CONCEPTS) == ["XP의 핵심 가치"]

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


def test_앞_문장을_가리키는_빈칸은_버린다():
    # 실측: 다시 설명용 빈칸에서 '그런 상황에서 쓰는 것이 ____ 다.'가 6화면 중 4번.
    # 글자 수 가드는 통과한다 — 짧아서가 아니라 '그런 상황'이 문장 안에 없어서
    # 못 푸는 것이다. 빈칸은 설명을 덮고 답하는 자리라 혼자 서야 한다.
    bad = [
        {"sentence": "그런 상황에서 쓰는 것이 ____ 이다.", "answer": "XP",
         "concept": "XP의 핵심 가치", "kind": "상황"},
    ]
    assert not [b for b in parse_response(_raw(cloze=bad), CONCEPTS) if b.type == "cloze"]


def test_문장_안에_단서가_있으면_남긴다():
    ok = [
        {"sentence": "다섯 가지 핵심 가치를 강조하는 개발 방법론은 ____ 이다.",
         "answer": "XP의 핵심 가치", "concept": "XP의 핵심 가치", "kind": "상황"},
    ]
    assert [b for b in parse_response(_raw(cloze=ok), CONCEPTS) if b.type == "cloze"]
