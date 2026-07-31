"""Problem 유형별 형식 검증 테스트.

문제은행이 한 유형뿐이면 20문제만 풀어도 지겹고 추측으로 뚫린다. 유형을 넷으로
늘리면서 정답 자료형이 갈렸고(mcq·ox=문자열, multi·order=배열), LLM이 라벨로
답하거나 다중정답을 하나만 주는 사고가 잦아 형식 단계에서 확정 차단한다.
"""
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.problems.schemas import Problem, ProblemType  # noqa: E402


@contextmanager
def rejects():
    """형식 위반이면 예외가 나야 한다 (pytest 없이 실행하기 위한 최소 헬퍼)."""
    try:
        yield
    except Exception:
        return
    raise AssertionError("검증을 통과했다 — 폐기되어야 하는 문항이다")

OPTS = ["First Fit", "Best Fit", "Worst Fit", "요구 반입"]


def _make(**over):
    base = dict(
        level=2,
        type="mcq",
        question="배치 전략 중 단편화를 최소화하는 방식은?",
        options=OPTS,
        answer="Best Fit",
        explanation="최적 적합이 단편화를 최소화한다.",
        source_evidence="단편화를 '최소화'하는 분할 영역에 데이터 배치",
    )
    base.update(over)
    return Problem.model_validate(base)


# ── mcq ──────────────────────────────────────────────────────────────
def test_mcq_ok():
    p = _make()
    assert p.type is ProblemType.MCQ and p.answer_texts == ["Best Fit"]


def test_mcq_answer_not_in_options_rejected():
    with rejects():
        _make(answer="Next Fit")


def test_mcq_label_answer_rejected():
    # LLM이 보기 텍스트 대신 라벨("C")로 답하는 실측 사고.
    with rejects():
        _make(answer="C")


def test_mcq_list_answer_rejected():
    with rejects():
        _make(answer=["Best Fit"])


def test_duplicate_options_rejected():
    with rejects():
        _make(options=["Best Fit", "Best Fit", "First Fit", "Worst Fit"])


# ── multi ────────────────────────────────────────────────────────────
def test_multi_ok():
    p = _make(type="multi", answer=["First Fit", "Best Fit"])
    assert p.answer_texts == ["First Fit", "Best Fit"]


def test_multi_single_answer_rejected():
    # 정답이 하나면 그건 mcq다.
    with rejects():
        _make(type="multi", answer=["Best Fit"])


def test_multi_all_options_rejected():
    # 보기 전부가 정답이면 고를 것이 없다 — 실측된 결함 유형.
    with rejects():
        _make(type="multi", answer=list(OPTS))


def test_multi_unknown_item_rejected():
    with rejects():
        _make(type="multi", answer=["Best Fit", "Next Fit"])


# ── ox ───────────────────────────────────────────────────────────────
def test_ox_ok_and_options_cleared():
    # 보기를 실어 보내도 무의미하므로 비운다(화면은 O/X 고정 렌더).
    p = _make(type="ox", answer="O", options=["참", "거짓"])
    assert p.answer == "O" and p.options == []


def test_ox_invalid_answer_rejected():
    with rejects():
        _make(type="ox", answer="참", options=[])


# ── order ────────────────────────────────────────────────────────────
def test_order_ok():
    seq = ["요구 반입", "First Fit", "Best Fit", "Worst Fit"]
    p = _make(type="order", answer=seq)
    assert p.answer_texts == seq


def test_order_partial_sequence_rejected():
    # 보기 일부만 나열하는 실측 사고 — 전체의 순열이어야 한다.
    with rejects():
        _make(type="order", answer=["Best Fit", "Worst Fit"])


def test_order_unknown_item_rejected():
    with rejects():
        _make(type="order", answer=["Best Fit", "Worst Fit", "First Fit", "Next Fit"])


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
