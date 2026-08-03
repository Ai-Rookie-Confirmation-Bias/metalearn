"""절 묶기 단위 테스트 — 실제 파싱 출력(pilgi.pdf 조각 #0)으로 검증.

여기가 틀리면 커리큘럼 전체가 틀어진다. 절이 학습 단위이자 생성 단위이고,
진단 가중치와 형성평가 범위도 절을 기준으로 잡기 때문이다.

샘플은 정보처리기사 요약집 1과목 조각 #0의 개념 18개를 그대로 옮긴 것이다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.curriculum.grouping import (  # noqa: E402
    Concept,
    group_into_sections,
)

# 실제 파싱 결과 — `이름 — 정의 · 선수: X, Y` 를 그대로 옮겼다.
# order는 원문 등장 순서(항목 번호 001, 002 … 를 따름).
SAMPLE = [
    Concept("소프트웨어 공학의 기본 원칙", "품질 유지를 위해 지속 적용할 원칙들", (), 1),
    Concept("폭포수 모형", "이전 단계로 돌아갈 수 없는 고전적 생명주기", ("소프트웨어 생명 주기",), 2),
    Concept("애자일 개발 4가지 핵심 가치", "개인·실행·협업·변화 대응", ("애자일 개발",), 5),
    Concept("XP의 핵심 가치", "XP의 5가지 핵심 가치", ("애자일 개발", "XP"), 6),
    Concept("요구사항 개발 프로세스", "도출·분석·명세·확인", (), 10),
    Concept("UML", "표준화된 객체지향 모델링 언어", ("객체지향 모델링",), 20),
    Concept("구조적 다이어그램", "시스템의 정적 구조 표현", ("UML",), 21),
    Concept("행위 다이어그램", "시스템의 동적 행동 표현", ("UML",), 22),
    Concept("유스케이스 다이어그램", "액터와 기능의 상호작용", ("UML", "시스템 액터"), 23),
    Concept("순차 다이어그램", "시간 순서에 따른 메시지 교환", ("UML",), 24),
    Concept("자료 흐름도", "프로세스·자료흐름·저장소·단말", ("자료 사전",), 30),
    Concept("자료 사전", "자료 흐름도 구성요소 정의", ("자료 흐름도",), 31),
    Concept("HIPO", "하향식 개발 문서화 도구", ("하향식 개발",), 35),
    Concept("사용자 인터페이스", "사용자와 시스템의 매개체", ("소프트웨어 설계",), 40),
    Concept("사용자 인터페이스 유형", "CLI, GUI, NUI 등", ("사용자 인터페이스",), 41),
    Concept("사용자 인터페이스의 기본 원칙", "직관성·유효성·학습성", ("사용자 인터페이스",), 42),
    Concept("목업", "와이어프레임보다 실제에 가까운 정적 모형", ("와이어프레임",), 45),
    Concept("ISO/IEC 9126 품질 특성", "기능성·신뢰성·사용성·이식성", ("소프트웨어 품질",), 50),
]


def _find(sections, key):
    """개념 key가 속한 절을 찾는다."""
    for s in sections:
        if any(c.key == key for c in s.concepts):
            return s
    raise AssertionError(f"'{key}'가 어느 절에도 없다")


def test_모든_개념이_정확히_한_절에_들어간다():
    # 개념이 누락되면 그 내용을 영영 안 배우고, 중복되면 같은 걸 두 번 배운다.
    sections = group_into_sections(SAMPLE)
    keys = [c.key for s in sections for c in s.concepts]
    assert len(keys) == len(SAMPLE), f"개념 수 불일치: {len(keys)} != {len(SAMPLE)}"
    assert len(set(keys)) == len(keys), "같은 개념이 두 절에 들어갔다"


def test_UML_다이어그램들이_UML과_한_절로():
    # 실측 근거: 넷이 UML을 선수로 공유한다. 따로 배우면 서로 무관해 보인다.
    sections = group_into_sections(SAMPLE)
    uml = _find(sections, "구조적 다이어그램")
    names = {c.key for c in uml.concepts}
    assert names == {
        "UML",
        "구조적 다이어그램",
        "행위 다이어그램",
        "유스케이스 다이어그램",
        "순차 다이어그램",
    }, names


def test_사용자_인터페이스가_한_절로():
    sections = group_into_sections(SAMPLE)
    ui = _find(sections, "사용자 인터페이스 유형")
    names = {c.key for c in ui.concepts}
    assert names == {
        "사용자 인터페이스",
        "사용자 인터페이스 유형",
        "사용자 인터페이스의 기본 원칙",
    }, names


def test_부모가_목록에_없어도_묶인다():
    # '애자일 개발'은 개념으로 안 잡혔지만, 그걸 공유하는 둘은 같이 배워야 한다.
    sections = group_into_sections(SAMPLE)
    agile = _find(sections, "XP의 핵심 가치")
    assert any(c.key == "애자일 개발 4가지 핵심 가치" for c in agile.concepts), (
        [c.key for c in agile.concepts]
    )


def test_순환은_한_절로():
    # 자료 흐름도 ↔ 자료 사전. 순서를 정할 수 없으니 함께 본다.
    sections = group_into_sections(SAMPLE)
    s = _find(sections, "자료 흐름도")
    names = {c.key for c in s.concepts}
    assert names == {"자료 흐름도", "자료 사전"}, names
    assert "선수" in s.reason


def test_외톨이는_원문_순서로_묶인다():
    sections = group_into_sections(SAMPLE)
    s = _find(sections, "소프트웨어 공학의 기본 원칙")
    orders = [c.order for c in s.concepts]
    assert orders == sorted(orders), "절 안에서 원문 순서가 깨졌다"
    assert len(s.concepts) >= 2, "혼자 남은 절은 학습 단위로 너무 작다"


def test_절_순서가_원문을_따른다():
    # 학습 순서가 교재와 어긋나면 어디를 보고 있는지 혼란스럽다.
    sections = group_into_sections(SAMPLE)
    firsts = [min(c.order for c in s.concepts) for s in sections]
    assert firsts == sorted(firsts), firsts


def test_절_크기가_학습_단위로_적당하다():
    sections = group_into_sections(SAMPLE)
    for s in sections:
        assert 1 <= s.size <= 10, f"'{s.title}' 절이 {s.size}개"
    # 18개가 3~8개 절로 — 너무 잘면 진도가 끊기고, 너무 크면 한 화면에 안 담긴다.
    assert 3 <= len(sections) <= 8, f"절 {len(sections)}개"


def test_모든_절에_묶인_이유가_있다():
    # 판단을 규칙이 하므로 이유를 화면에 쓸 수 있다 — 서비스 정의의 전제.
    for s in group_into_sections(SAMPLE):
        assert s.reason, f"'{s.title}'에 이유가 없다"


def test_결정적이다():
    # 입력 순서가 바뀌어도 같은 결과여야 "왜 이렇게 묶였는지"를 고정해 쓸 수 있다.
    a = group_into_sections(SAMPLE)
    b = group_into_sections(list(reversed(SAMPLE)))
    assert [(s.title, tuple(c.key for c in s.concepts)) for s in a] == [
        (s.title, tuple(c.key for c in s.concepts)) for s in b
    ]


def test_빈_입력():
    assert group_into_sections([]) == []


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
