"""화면 슬라이스 단위 테스트.

절 묶기 엔진은 폐기했다. 여기서 보장하는 건:
  · 모든 개념이 정확히 한 화면에
  · 원문/order 순 유지
  · 화면 크기 2~4 (SCREEN_SIZE=3, 끝 1개 병합)
  · 결정적 (입력 순서 무관)
의미 묶음(UML 한 절 등)은 더 이상 이 모듈의 일이 아니다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.curriculum.grouping import (  # noqa: E402
    SCREEN_SIZE,
    Concept,
    group_into_sections,
)

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


def test_모든_개념이_정확히_한_화면에():
    screens = group_into_sections(SAMPLE)
    keys = [c.key for s in screens for c in s.concepts]
    assert len(keys) == len(SAMPLE)
    assert len(set(keys)) == len(keys)


def test_원문_order_순으로_자른다():
    screens = group_into_sections(SAMPLE)
    flat = [c.key for s in screens for c in s.concepts]
    expected = [c.key for c in sorted(SAMPLE, key=lambda c: (c.order, c.key))]
    assert flat == expected


def test_화면_크기는_2_to_4():
    screens = group_into_sections(SAMPLE)
    for s in screens:
        assert 2 <= s.size <= SCREEN_SIZE + 1, f"'{s.title}' size={s.size}"
    # 18개 / 3 = 6화면
    assert len(screens) == 6


def test_끝_혼자_남으면_앞에_붙인다():
    # 4개 → 3+1 이 아니라 4 한 화면
    four = SAMPLE[:4]
    screens = group_into_sections(four)
    assert len(screens) == 1
    assert screens[0].size == 4


def test_화면_순서가_order를_따른다():
    screens = group_into_sections(SAMPLE)
    firsts = [min(c.order for c in s.concepts) for s in screens]
    assert firsts == sorted(firsts)


def test_슬라이스는_거짓_이유를_안_붙인다():
    # ⚡는 규칙이 조정한 것만. 단순 자르기에 이유를 붙이면 속이 빈 표시가 된다.
    for s in group_into_sections(SAMPLE):
        assert s.reason == ""


def test_결정적이다():
    a = group_into_sections(SAMPLE)
    b = group_into_sections(list(reversed(SAMPLE)))
    assert [(s.title, tuple(c.key for c in s.concepts)) for s in a] == [
        (s.title, tuple(c.key for c in s.concepts)) for s in b
    ]


def test_빈_입력():
    assert group_into_sections([]) == []


def test_원문_있으면_등장_위치로_정렬():
    # order는 뒤집혀 있어도 원문 등장 순을 따른다.
    concepts = [
        Concept("나중", "", (), order=1),
        Concept("먼저", "", (), order=2),
    ]
    source = "먼저 나오고 그 다음 나중 개념"
    screens = group_into_sections(concepts, source)
    assert [c.key for c in screens[0].concepts] == ["먼저", "나중"]


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
