"""BKT(Bayesian Knowledge Tracing) 순수 계층 — P(known) 추정 (ISSUE-010).

DB/ORM/LLM에 의존하지 않는다. 호출측이 attempts 이력(정오 시퀀스)과 선행 P(known)을
넘기면, 이 모듈이 개념의 숙련 확률 P(known)을 추정한다.

왜 BKT인가 (설계 근거, WORK_LOG 2026-07-06):
- "모름 감지"는 "앎 감지"보다 어렵다(틀림의 원인이 slip/guess/결손/오개념 등 다수) →
  P(S)(slip)·P(G)(guess)로 노이즈를 흡수한다.
- 표준 BKT는 개념 독립을 가정 → 국소화 불가. 그래서 **P(L0)를 선행들의 P(known)으로
  결합(BKT×DAG)**: 선행이 약하면 이 개념의 사전확률을 낮춰 "실패가 예상된 것"이 되게 하고,
  blame이 선행으로 흐르도록 한다. (국소화 판정은 localization.py)

※ 파라미터는 콜드스타트 풀링값(휴리스틱). 개념유형/depth별 개별화는 후속.
"""
from __future__ import annotations

# 표준 BKT 4파라미터 (개념유형 무관 풀링 기본값 — 후속 개별화 대상)
P_TRANSIT = 0.15  # P(T): 한 번 접한 뒤 학습될 확률
P_SLIP = 0.10     # P(S): 알지만 틀릴 확률
P_GUESS = 0.20    # P(G): 모르지만 맞힐 확률

# P(L0) 사전확률: 선행이 완전히 알려졌을 때의 상한(준비됨) / 선행 없을 때 콜드스타트 기본
_P_L0_BASE = 0.30
_P_L0_FLOOR = 0.05  # 선행이 완전 미지여도 0은 아님(측정 노이즈 여지)


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def p_l0_from_prereqs(prereq_p_knowns: list[float]) -> float:
    """선행들의 P(known)으로 이 개념의 사전확률 P(L0)을 결정(BKT×DAG 결합).

    선행이 여럿이면 **가장 약한 선행(weakest link)** 을 기준으로 한다 — 사슬은
    가장 약한 고리만큼만 강하다. 선행이 없으면(리프) 풀링 기본값.

      선행 없음        → _P_L0_BASE
      선행 전부 known  → _P_L0_BASE
      선행 약함        → _P_L0_BASE * weakest (하한 _P_L0_FLOOR)
    """
    if not prereq_p_knowns:
        return _P_L0_BASE
    weakest = min(_clamp01(p) for p in prereq_p_knowns)
    return max(_P_L0_FLOOR, round(_P_L0_BASE * weakest, 4))


def _observe(p_prev: float, correct: bool) -> float:
    """관측 1개(정/오)로 사후확률 갱신 후, 학습 전이(P_T) 적용 → 다음 P(L)."""
    if correct:
        num = p_prev * (1 - P_SLIP)
        den = num + (1 - p_prev) * P_GUESS
    else:
        num = p_prev * P_SLIP
        den = num + (1 - p_prev) * (1 - P_GUESS)
    posterior = num / den if den > 0 else p_prev
    return _clamp01(posterior + (1 - posterior) * P_TRANSIT)


def estimate_p_known(outcomes: list[bool], *, p_l0: float) -> float:
    """정오 시퀀스(시간순)를 P(L0)에서 시작해 BKT로 접어 P(known)을 추정.

    outcomes가 비면(시도 없음) 사전확률을 그대로 반환한다.
    """
    p = _clamp01(p_l0)
    for correct in outcomes:
        p = _observe(p, correct)
    return round(p, 4)
