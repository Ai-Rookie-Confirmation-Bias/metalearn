"""문항 정답 유출 방어 단위 테스트 (Tier 2 ③).

개념명은 절 제목·블록 제목으로 화면에 노출되므로, 정답이 개념명에 통째로
담긴 문항은 지문 없이도 풀린다 → 폐기한다. 단 부분 포함(힌트 수준)은 살린다.
"""
import pytest

from app.features.learning.generator import (
    check_cloze_deterministic,
    _mcq_answer_leaked,
)


# ── cloze: 개념명 유출 → 폐기(None) ──
@pytest.mark.parametrize(
    "blanks, concept",
    [
        (["X.400"], "X.400"),            # 정답 == 개념명
        (["X.400"], "X.400 프로토콜"),    # 정답 ⊂ 개념명(제목에 노출)
    ],
)
def test_cloze_concept_leak_dropped(blanks, concept):
    data = {"text": "표준은 {{blank}}이다", "blanks": blanks}
    assert check_cloze_deterministic(data, concept) is None


# ── cloze: 정상·부분포함 → 유지(과잉폐기 금지) ──
@pytest.mark.parametrize(
    "blanks, concept",
    [
        (["네트워크"], "OSI 참조 모델"),        # 개념명과 무관
        (["X.400 프로토콜"], "X.400"),          # 개념명 ⊂ 정답(부분 힌트뿐)
    ],
)
def test_cloze_valid_kept(blanks, concept):
    data = {"text": "이것은 {{blank}}", "blanks": blanks}
    assert check_cloze_deterministic(data, concept) is not None


def test_cloze_self_reference_still_dropped():
    # 기존 자기참조(본문에 정답) 방어는 유지
    data = {"text": "네트워크는 {{blank}}, 즉 네트워크다", "blanks": ["네트워크"]}
    assert check_cloze_deterministic(data, "무관개념") is None


# ── mcq: 정답 보기 유출 판정 ──
def test_mcq_answer_is_concept_leaks():
    assert _mcq_answer_leaked({"options": ["TCP", "X.400"], "answerIndex": 1}, "X.400") is True


def test_mcq_answer_in_concept_leaks():
    assert _mcq_answer_leaked({"options": ["A", "X.400"], "answerIndex": 1}, "X.400 표준") is True


def test_mcq_unrelated_answer_ok():
    assert _mcq_answer_leaked({"options": ["물리계층", "전송계층"], "answerIndex": 1}, "OSI 역할") is False


def test_mcq_wrong_option_is_concept_ok():
    # 정답이 아닌 보기가 개념명이어도 정답만 검사하므로 유출 아님
    assert _mcq_answer_leaked({"options": ["X.400", "TCP"], "answerIndex": 1}, "X.400") is False
