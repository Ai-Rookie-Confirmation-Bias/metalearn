"""grounding.evidence_in_source 단위 테스트.

문제 생성 에이전트의 1차 방어선(원문 대조) 회귀 방지. 순수 로직이라
외부 의존이 없어 pytest 없이도 `python3 tests/test_grounding.py`로 돈다.
핵심 회귀 케이스: 원문 곳곳의 단어를 긁어모아 만든 '창작' 근거는 폐기돼야 한다
(구 폴백은 앞 12자만 맞으면 통과시켜 이 경계가 뚫려 있었다).
"""
import sys
from pathlib import Path

# backend/ 를 import 경로에 올린다(pytest·직접실행 모두 대응).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.problems.grounding import (  # noqa: E402
    answer_stands_out,
    evidence_in_source,
    items_not_in_source,
)

# 실제 파싱 출력을 모사한 표 마크다운 원문(불릿·파이프 포함).
SOURCE = """## 페이지 교체 전략

| 전략 | 종류 | 설명 |
| --- | --- | --- |
| FIFO | 큐 | 가장 먼저 적재된 페이지를 먼저 교체한다 |
| LRU | 스택 | 가장 오래 참조되지 않은 페이지를 교체한다 |

- 벨레이디의 역설: FIFO에서 프레임 수를 늘려도 페이지 폴트가 늘 수 있다.
"""


def test_exact_quote_passes():
    assert evidence_in_source("가장 오래 참조되지 않은 페이지를 교체한다", SOURCE)


def test_bulleted_quote_passes():
    # 불릿 기호가 붙은 원문을, 기호 없이 인용해도 통과해야 한다.
    assert evidence_in_source(
        "벨레이디의 역설: FIFO에서 프레임 수를 늘려도 페이지 폴트가 늘 수 있다.",
        SOURCE,
    )


def test_table_cell_quote_passes():
    # 파이프로 둘러싸인 표 셀 내용을 인용해도 정규화 후 통과.
    assert evidence_in_source("가장 먼저 적재된 페이지를 먼저 교체한다", SOURCE)


def test_scattered_fabrication_rejected():
    # 원문 단어들을 흩어 모아 만든 거짓 주장 — 반드시 폐기.
    assert not evidence_in_source(
        "LRU는 가장 먼저 적재된 페이지를 먼저 교체한다", SOURCE
    )


def test_out_of_source_claim_rejected():
    # 원문에 없는 내용 — 폐기.
    assert not evidence_in_source(
        "클럭 알고리즘은 참조 비트를 사용해 페이지를 교체한다", SOURCE
    )


def test_too_short_rejected():
    # 근거 구실 못 하는 짧은 조각은 폐기.
    assert not evidence_in_source("FIFO", SOURCE)


def test_empty_rejected():
    assert not evidence_in_source("", SOURCE)
    assert not evidence_in_source("아무 내용", "")


# ── L3(비교·종합) 회귀 — 원문 두 곳을 이어 인용하는 경우 ──────────────
# 셀·불릿 내용이 마침표로 끝나지 않아, 문장 분리를 마침표에만 의존하던
# 구현에서는 조각이 1개로 남아 전량 폐기됐다(실측 L3 0/2).
MULTI_SOURCE = """### ■ 페이지 분할 기법

**1) 페이징 기법 (Paging)**

- 프로그램을 동일 크기로 분할 (내부 단편화 발생 가능성 존재)

**2) 세그먼테이션 기법 (Segmentation)**

- 프로그램을 다양한 크기의 논리적 단위로 분할 (외부 단편화 발생 가능성 존재)
"""


def test_multi_location_quote_passes():
    # 떨어진 두 곳을 줄바꿈으로 구분해 인용 — 조각 전부 실재하므로 통과.
    assert evidence_in_source(
        "프로그램을 동일 크기로 분할 (내부 단편화 발생 가능성 존재)\n"
        "프로그램을 다양한 크기의 논리적 단위로 분할 (외부 단편화 발생 가능성 존재)",
        MULTI_SOURCE,
    )


def test_multi_location_with_fabricated_half_rejected():
    # 두 조각 중 하나가 창작이면 폐기 — 조각 전수 검사가 살아있는지 확인.
    assert not evidence_in_source(
        "프로그램을 동일 크기로 분할 (내부 단편화 발생 가능성 존재)\n"
        "세그먼테이션 기법은 내부 단편화가 발생한다",
        MULTI_SOURCE,
    )


def test_table_row_quote_passes():
    # 표 한 행을 파이프째 인용 — 셀 경계로 쪼개 조각별 대조.
    assert evidence_in_source(
        "| LRU | 스택 | 가장 오래 참조되지 않은 페이지를 교체한다 |", SOURCE
    )


# ── 보기 창작 차단 — 근거만 대조하면 놓치는 구멍 ────────────────────
def test_fabricated_options_detected():
    """실측 회귀: 근거는 원문 한 줄을 인용하면서 보기에는 원문에 없는 단계를
    지어내 배열시킨 순서 문항이 게이트를 통과했다.

    부분 문자열 판정이라 짧고 일반적인 문구("페이지 교체")는 원문의 다른 맥락
    (제목 "페이지 교체 전략")에 우연히 포함될 수 있다. 그래도 **하나라도**
    창작이 잡히면 문항 전체가 폐기되므로 방어는 성립한다.
    """
    missing = items_not_in_source(
        ["페이지 참조", "교체 전략 선택", "페이지 교체", "페이지 적재"], SOURCE
    )
    assert "페이지 참조" in missing and "교체 전략 선택" in missing
    assert missing  # 비어 있지 않음 → 그 문항은 폐기된다


def test_real_options_pass():
    # 원문에 실재하는 짧은 보기는 통과해야 한다(근거보다 짧아도 허용).
    assert items_not_in_source(["FIFO", "LRU", "벨레이디의 역설"], SOURCE) == []


def test_partially_fabricated_options():
    missing = items_not_in_source(["FIFO", "클럭 알고리즘"], SOURCE)
    assert missing == ["클럭 알고리즘"]


def test_answer_stands_out_catches_giveaway():
    # 실측 사례: 원문에 "예상 반입"이라는 진짜 짝이 있는데도 오답을 전부 지어냈다.
    # 원문을 읽은 학습자는 내용을 몰라도 "읽어본 문장"만 고르면 맞힌다.
    assert answer_stands_out(
        ["FIFO"],
        ["FIFO", "클럭 알고리즘", "이차 기회 알고리즘", "랜덤 교체"],
        SOURCE,
    )


def test_answer_stands_out_passes_when_distractors_are_real():
    # 오답이 원문의 다른 항목이면 정상 문항이다.
    assert not answer_stands_out(["FIFO"], ["FIFO", "LRU"], SOURCE)


def test_answer_stands_out_needs_only_one_real_distractor():
    # 원문 서술을 비틀어 만든 오답은 글자로는 원문 밖이지만 학습적으로 타당하다.
    # 하나라도 진짜가 섞여 있으면 통과시킨다.
    assert not answer_stands_out(
        ["FIFO"], ["FIFO", "LRU", "클럭 알고리즘", "랜덤 교체"], SOURCE
    )


def test_answer_stands_out_ignores_optionless_and_fabricated_answer():
    assert not answer_stands_out(["O"], [], SOURCE)  # ox — 볼 보기가 없다
    # 정답조차 원문 밖이면 이 게이트가 아니라 근거 대조가 잡을 일이다.
    assert not answer_stands_out(
        ["클럭 알고리즘"], ["클럭 알고리즘", "이차 기회"], SOURCE
    )


def test_answer_stands_out_handles_multi():
    # 정답이 여럿이어도 같은 규칙 — 오답 전부가 창작이면 결함이다.
    assert answer_stands_out(
        ["FIFO", "LRU"], ["FIFO", "LRU", "클럭 알고리즘", "랜덤 교체"], SOURCE
    )


def _main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError:
            failed += 1
            print(f"FAIL {t.__name__}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_main())
