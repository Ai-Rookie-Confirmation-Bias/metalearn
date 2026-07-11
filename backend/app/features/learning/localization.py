"""원인 국소화 순수 계층 — "왜 틀렸나" 판정 (ISSUE-010).

DB/LLM 비의존. 입력: 대상 개념의 P(known)·시도수·확신도 + 선행들의 (id, P(known), depth).
출력: 원인 분류 Cause.

설계(WORK_LOG 2026-07-06):
- 단일 임계 금지 → (대상 P(known) · 시도수 · 선행 P(known)) 조합으로 판정.
- 근거 부족(시도 적음)이면 **판단 보류(hold)** — 오탐 방지.
- 선행이 약하면 **선수결손(prerequisite)**, blame은 **최상류(가장 근본) 약한 선행**에.
  parsing 규약상 근본 선수일수록 depth가 **크다** → 최상류 = **최대 depth**.
  (신호는 엣지로만 전파 — 이 함수는 대상의 직접 선행만 받는다)
- 선행은 튼튼한데 대상만 약하면 **본문 결손(content)**.
- 오개념(misconception)은 서술 채점 근거가 필요 → 여기선 훅만(입력 misconception_signal).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, NamedTuple

CauseType = Literal["hold", "prerequisite", "content", "misconception", "ok"]

# 판정 임계 (조합 규칙 — 후속 튜닝 대상)
MIN_ATTEMPTS_TO_JUDGE = 2  # 이보다 적으면 판단 보류
PREREQ_WEAK_TH = 0.5       # 선행 P(known)이 이 아래면 '약한 선행'
TARGET_WEAK_TH = 0.5       # 대상 P(known)이 이 아래면 '대상 약함'


class PrereqState(NamedTuple):
    concept_id: str
    p_known: float
    depth: int  # DAG depth — parsing 규약: 근본 선수일수록 큼(최상류=최대 depth)


@dataclass(frozen=True)
class Cause:
    """국소화 결과. blame_concept_id는 prerequisite일 때만 채워진다."""

    type: CauseType
    reason: str
    blame_concept_id: str | None = None


def localize(
    *,
    target_p_known: float,
    target_attempts: int,
    prereqs: list[PrereqState],
    misconception_signal: bool = False,
) -> Cause:
    """대상 개념 실패의 원인을 국소화한다.

    호출측은 보통 '틀린 직후'에 부른다. 정답이어도 부를 수 있고, 그땐 ok로 떨어진다.
    """
    if target_attempts < MIN_ATTEMPTS_TO_JUDGE:
        return Cause(
            type="hold",
            reason=f"근거 부족(시도 {target_attempts} < {MIN_ATTEMPTS_TO_JUDGE}) — 판단 보류",
        )

    # 오개념: 보충 진단(ISSUE-005) 신호가 있으면 우선(처방이 선행 삽입이 아니라
    # 재설명 지속으로 다름 — 개념을 '잘못' 이해한 건 선행 결손과 별개 문제)
    if misconception_signal:
        return Cause(type="misconception", reason="직전 보충 진단에서 오개념 신호 감지")

    weak = [p for p in prereqs if p.p_known < PREREQ_WEAK_TH]
    if weak:
        # 최상류(가장 근본 = parsing 규약상 최대 depth) 약한 선행에 blame — 근본부터 보충
        blame = max(weak, key=lambda p: (p.depth, -p.p_known))
        return Cause(
            type="prerequisite",
            reason=(
                f"선행 {blame.concept_id[:8]}… P(known)={blame.p_known:.2f} 약함 "
                f"(depth {blame.depth}) — 최상류 결손"
            ),
            blame_concept_id=blame.concept_id,
        )

    if target_p_known < TARGET_WEAK_TH:
        return Cause(
            type="content",
            reason=f"선행은 충분하나 대상 P(known)={target_p_known:.2f} 약함 — 본문 결손",
        )

    return Cause(
        type="ok", reason=f"대상 P(known)={target_p_known:.2f} 충분 — 국소화 불필요"
    )
