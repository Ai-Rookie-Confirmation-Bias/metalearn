"""BKT(Bayesian Knowledge Tracing) 순수 로직.

부수효과/DB 의존 없는 순수 함수 모음. 진단 서비스가 호출한다.

표기:
  p          현재 숙련 확률 P(L_n = 안다)
  p_slip     슬립: 알면서 틀릴 확률  P(오답 | 안다)
  p_guess    추측: 모르면서 맞힐 확률 P(정답 | 모른다)
  p_transit  학습전이: 모름→앎 전이 확률 (진단 모드에선 0 권장)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BKTParams:
    p_init: float
    p_transit: float
    p_slip: float
    p_guess: float


def update(p: float, *, correct: bool, params: BKTParams) -> float:
    """관측(정/오답) 1건으로 숙련 확률을 갱신한다.

    1) 베이즈 사후확률 P(L | 관측)
    2) 학습전이 반영 P(L_{n+1}) = cond + (1-cond)*p_transit
    """
    if correct:
        num = p * (1.0 - params.p_slip)
        den = num + (1.0 - p) * params.p_guess
    else:
        num = p * params.p_slip
        den = num + (1.0 - p) * (1.0 - params.p_guess)

    cond = num / den if den > 0 else p
    return cond + (1.0 - cond) * params.p_transit


def is_resolved(p: float, *, high: float, low: float) -> bool:
    """신뢰도 경계 확정 여부 (앎>=high 또는 모름<=low)."""
    return p >= high or p <= low


def uncertainty(p: float) -> float:
    """0.5에 가까울수록 큰 불확실성 점수(최대 0.5). 타겟팅 우선순위용."""
    return 0.5 - abs(p - 0.5)


# ── 그래프 전파 ───────────────────────────────────────────────────────────
def propagate(
    *,
    source_p: float,
    target_p: float,
    correct: bool,
    decay: float,
    hop: int,
) -> float:
    """한 개념의 정/오답에서 연결 개념으로 p_known을 전파한다 (순수 함수).

    정답(correct=True):
      선수 개념(prerequisite)은 이미 알고 있었을 가능성 ↑.
      target_p를 source_p 방향으로 부분 당김. 감쇠율 decay^hop 적용.

    오답(correct=False):
      후속 개념(dependent)을 모를 가능성 ↑.
      target_p를 source_p 방향으로 부분 당김. 감쇠율 decay^hop 적용.

    수식: new = target + (source - target) * decay^hop
    hop=0이면 source 자체라 변화 없이 source_p 반환.
    """
    strength = decay ** hop
    return target_p + (source_p - target_p) * strength


def propagate_up(
    *,
    answered_p: float,
    prereq_p: float,
    decay: float,
    hop: int = 1,
) -> float:
    """정답 후 선수 개념(prerequisite)으로 상향 전파.

    정답을 맞혔다면 선수 개념도 알고 있을 가능성이 높다.
    answered_p(높아진 값)를 선수 개념 쪽으로 당긴다.
    """
    return propagate(
        source_p=answered_p,
        target_p=prereq_p,
        correct=True,
        decay=decay,
        hop=hop,
    )


def propagate_down(
    *,
    answered_p: float,
    dependent_p: float,
    decay: float,
    hop: int = 1,
) -> float:
    """오답 후 후속 개념(dependent)으로 하향 전파.

    오답이라면 그 개념을 전제로 하는 상위 개념도 모를 가능성이 높다.
    answered_p(낮아진 값)를 후속 개념 쪽으로 당긴다.
    """
    return propagate(
        source_p=answered_p,
        target_p=dependent_p,
        correct=False,
        decay=decay,
        hop=hop,
    )
