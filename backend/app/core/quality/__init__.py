"""문항 품질 공통 모듈 — 어느 기능(문제은행·학습·진단·형성평가)에도 묶이지 않는다.

입력 계약: "문항(type+data) + 근거 텍스트 + LLM". 조각·목차·코스 개념 없음.
README 폴더 계획의 `core/verify_grade.py`(검증·채점 공통) 자리를 이 패키지가 맡는다.
"""
from app.core.quality.checks import mechanical_check, polish_mcq, strip_answers
from app.core.quality.grading import answer_payload, chosen_explanation, grade
from app.core.quality.types import CandidateItem, ItemVerdict, QualityConfig
from app.core.quality.validator import validate_items

__all__ = [
    "CandidateItem",
    "ItemVerdict",
    "QualityConfig",
    "validate_items",
    "mechanical_check",
    "polish_mcq",
    "strip_answers",
    "grade",
    "answer_payload",
    "chosen_explanation",
]
