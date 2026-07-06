"""Next-Action Router — 답변 결과 + 숙련도 → 다음 행동 (기획서 §2.5C, §6).

순수 규칙 계층. DB/LLM 의존 없음.

살아있는 커리큘럼:
  정답 + 높은 strength  → thin_pass  (compressed variant, §6)
  정답                  → advance
  오답 1회              → supplement (약점 등록 + 보충, taught 리셋)
  연속 오답 2회+        → prerequisite (선행 챕터 삽입)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.features.learning.mastery import MasteryState

ActionType = Literal["advance", "thin_pass", "supplement", "prerequisite"]

THIN_PASS_STRENGTH = 0.85
PREREQ_WRONG_THRESHOLD = 2


@dataclass(frozen=True)
class NextAction:
    action: ActionType
    reason: str


def decide_after_answer(
    *,
    state: MasteryState,
    is_correct: bool,
) -> NextAction:
    """채점 직후 호출. state는 이미 apply_*_attempt 반영된 스냅샷."""
    strength = state.strength
    consecutive_wrong = state.consecutive_wrong

    if is_correct:
        if strength >= THIN_PASS_STRENGTH:
            return NextAction(
                action="thin_pass",
                reason=f"strength {strength:.2f} — compressed variant",
            )
        return NextAction(
            action="advance",
            reason=f"correct — next section (strength {strength:.2f})",
        )

    if consecutive_wrong >= PREREQ_WRONG_THRESHOLD:
        return NextAction(
            action="prerequisite",
            reason=f"{consecutive_wrong} consecutive wrong — insert prerequisite chapter",
        )

    return NextAction(
        action="supplement",
        reason="incorrect — weakness registered, supplement same concept",
    )


def decide_intervention_stage(*, consecutive_wrong: int, hints_used: int = 0) -> str:
    """선제 개입 단계 (§2.5C hintLadder).

    Returns: 'reframe' | 'hint_ladder' | 'prerequisite_review' | 'none'
    """
    if consecutive_wrong >= PREREQ_WRONG_THRESHOLD:
        return "prerequisite_review"
    if consecutive_wrong >= 1 and hints_used >= 1:
        return "hint_ladder"
    if consecutive_wrong >= 1:
        return "reframe"
    return "none"
