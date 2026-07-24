"""제출 답안 형식 검증(validate_user_input) 단위 테스트.

형식오류(잘못된 구조)는 ValueError(→라우터 422)로 거부하고, '빈 답'·'틀린 답'
같은 정상 오답은 통과시켜 채점되게 한다(ISSUE-005 후속: 조용한 오답 오염 방지).
"""
import pytest

from app.features.learning.grading import validate_user_input


# ── 정상 형식은 통과(예외 없음) ──
@pytest.mark.parametrize(
    "block_type, user_input",
    [
        ("mcq", 2),           # 보기 인덱스
        ("mcq", "3"),         # 문자열 인덱스(레거시 허용)
        ("mcq", 0),           # 첫 보기
        ("cloze", ["답1", "답2"]),   # 빈칸별 배열
        ("cloze", "답1,답2"),        # 콤마 문자열(레거시)
        ("cloze", ["", ""]),         # 빈 답(정상 오답)
        ("cloze", []),               # 빈 배열(정상 오답)
        ("explainBack", "내 설명"),
        ("explainBack", ""),          # 빈 텍스트(정상 오답)
        ("reviewGate", "복습 답"),
    ],
)
def test_valid_shapes_pass(block_type, user_input):
    validate_user_input(block_type, user_input)  # 예외가 나지 않아야 한다


# ── 형식오류는 거부(ValueError) ──
@pytest.mark.parametrize(
    "block_type, user_input",
    [
        ("mcq", None),          # 미선택
        ("mcq", ["a"]),         # 리스트
        ("mcq", {"x": 1}),      # dict
        ("mcq", "abc"),         # 비정수 문자열
        ("mcq", True),          # bool
        ("cloze", {"x": 1}),    # dict
        ("cloze", 5),           # 숫자
        ("cloze", None),        # None
        ("cloze", True),        # bool
        ("explainBack", ["리스트"]),  # 리스트
        ("explainBack", {"x": 1}),   # dict
        ("explainBack", None),        # None
        ("explainBack", 5),           # 숫자
    ],
)
def test_malformed_shapes_raise(block_type, user_input):
    with pytest.raises(ValueError):
        validate_user_input(block_type, user_input)
