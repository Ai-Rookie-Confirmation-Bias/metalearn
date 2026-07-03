"""개념 숙련도 순수 로직 (기획서 concept_mastery 계층).

DB/ORM에 의존하지 않는다. 호출측이 concept_mastery 행을 읽고 쓸 때 이 함수로
strength·explanation_score·status·consecutive_wrong 등을 갱신한다.

strength = 정답률 기반 점수 + explainBack explanation_score 가중 합산(0~1).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone

from app.core.enums import MasteryStatus

_DEFAULT_STRENGTH = 0.0
_EXPLANATION_WEIGHT = 0.4  # explainBack 가중
_BOOLEAN_WEIGHT = 0.6
_MASTERED_THRESHOLD = 0.85
_LEARNING_THRESHOLD = 0.35


@dataclass(frozen=True)
class MasteryState:
    """concept_mastery 1행에 대응하는 스냅샷(순수 값 객체)."""

    strength: float = _DEFAULT_STRENGTH
    explanation_score: float = 0.0
    status: str = MasteryStatus.LOCKED
    consecutive_wrong: int = 0
    attempts: int = 0
    correct_count: int = 0
    difficulty: int = 1  # 1~3, JIT 생성 난이도 힌트(내부)
    taught: bool = False


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def recompute_strength(*, correct_count: int, attempts: int, explanation_score: float) -> float:
    """정답률 + explanation_score 가중 합산 → strength."""
    if attempts <= 0:
        bool_part = _DEFAULT_STRENGTH
    else:
        bool_part = correct_count / attempts
    expl_part = _clamp01(explanation_score)
    return round(_clamp01(_BOOLEAN_WEIGHT * bool_part + _EXPLANATION_WEIGHT * expl_part), 4)


def derive_status(state: MasteryState) -> str:
    if state.status == MasteryStatus.LOCKED:
        return MasteryStatus.LOCKED
    if state.strength >= _MASTERED_THRESHOLD and state.consecutive_wrong == 0:
        return MasteryStatus.MASTERED
    if state.attempts == 0 and state.status == MasteryStatus.TODO:
        return MasteryStatus.TODO
    if state.strength >= _LEARNING_THRESHOLD or state.attempts > 0:
        return MasteryStatus.LEARNING
    return state.status if state.status != MasteryStatus.LOCKED else MasteryStatus.TODO


def apply_boolean_attempt(state: MasteryState, *, correct: bool) -> MasteryState:
    """mcq/cloze/OX 등 boolean 채점 결과 반영."""
    attempts = state.attempts + 1
    correct_count = state.correct_count + (1 if correct else 0)
    consecutive_wrong = 0 if correct else state.consecutive_wrong + 1

    # ELO-lite: 최근 시도일수록 변화폭 축소
    k = max(0.08, 0.35 / (1 + attempts * 0.15))
    strength = state.strength
    if correct:
        strength = _clamp01(strength + k * (1.0 - strength))
        difficulty = min(3, state.difficulty + 1)
    else:
        strength = _clamp01(strength - k * strength)
        difficulty = max(1, state.difficulty - 1)

    explanation_score = state.explanation_score
    merged_strength = recompute_strength(
        correct_count=correct_count,
        attempts=attempts,
        explanation_score=explanation_score,
    )
    # boolean 시도는 즉시 strength에도 반영(가중 합산과 블렌드)
    strength = round(_clamp01(0.5 * strength + 0.5 * merged_strength), 4)

    next_state = replace(
        state,
        strength=strength,
        attempts=attempts,
        correct_count=correct_count,
        consecutive_wrong=consecutive_wrong,
        difficulty=difficulty,
    )
    return replace(next_state, status=derive_status(next_state))


def apply_scored_attempt(state: MasteryState, *, score: float) -> MasteryState:
    """explainBack 등 0~1 부분점수 반영 → explanation_score + strength 갱신."""
    score = _clamp01(score)
    attempts = state.attempts + 1
    # rubric 채점: 0.6 이상이면 '맞음'으로 카운트(부분점수 허용)
    correct = score >= 0.6
    correct_count = state.correct_count + (1 if correct else 0)
    consecutive_wrong = 0 if correct else state.consecutive_wrong + 1

    # explanation_score는 이동평균(최근 서술이 더 반영)
    prev = state.explanation_score
    explanation_score = round(_clamp01(prev * 0.4 + score * 0.6), 4)
    strength = recompute_strength(
        correct_count=correct_count,
        attempts=attempts,
        explanation_score=explanation_score,
    )

    next_state = replace(
        state,
        strength=strength,
        explanation_score=explanation_score,
        attempts=attempts,
        correct_count=correct_count,
        consecutive_wrong=consecutive_wrong,
    )
    return replace(next_state, status=derive_status(next_state))


def unlock_for_learning(state: MasteryState) -> MasteryState:
    """진단/커리큘럼에서 학습 대상으로 열 때 locked → todo."""
    if state.status != MasteryStatus.LOCKED:
        return state
    return replace(state, status=MasteryStatus.TODO)


def mark_taught(state: MasteryState) -> MasteryState:
    return replace(state, taught=True)


def reset_taught(state: MasteryState) -> MasteryState:
    """supplement(보충) 시 설명 블록을 다시 보여주기 위해."""
    return replace(state, taught=False)


def warm_start_from_diagnostic(
    state: MasteryState, *, correct: bool, initial_strength: float = 0.7
) -> MasteryState:
    """진단 1문항 결과로 초기 strength 시드( walk-down 스킵된 '안다' 판정 포함)."""
    if correct:
        seeded = replace(
            state,
            strength=_clamp01(initial_strength),
            explanation_score=state.explanation_score,
            attempts=max(1, state.attempts),
            correct_count=max(1, state.correct_count),
            consecutive_wrong=0,
            status=MasteryStatus.LEARNING,
        )
        return seeded
    return apply_boolean_attempt(unlock_for_learning(state), correct=False)
