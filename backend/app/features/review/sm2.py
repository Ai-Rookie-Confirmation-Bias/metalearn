"""SM-2 간격 반복 스케줄러 (기획서 concept_mastery.ease/interval_days/next_due_at).

순수 함수. DB 의존 없음. attempts(review) 결과로 next_due_at을 갱신할 때 사용.

표준 SM-2 quality(0~5)를 0~1 score/correct에 매핑:
  correct=True  → quality 4
  correct=False → quality 2
  explainBack score → round(score * 5) clamped 0~5
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class ReviewSchedule:
    ease: float
    interval_days: int
    next_due_at: datetime


def _quality_from_correct(correct: bool) -> int:
    return 4 if correct else 2


def _quality_from_score(score: float) -> int:
    return max(0, min(5, round(score * 5)))


def _sm2_ease_update(ease: float, quality: int) -> float:
    delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    return max(1.3, ease + delta)


def update_review_schedule(
    *,
    ease: float,
    interval_days: int,
    correct: bool | None = None,
    score: float | None = None,
    now: datetime | None = None,
    interval_factor: float = 1.0,
) -> ReviewSchedule:
    """한 번의 복습/학습 시도 후 SM-2 스케줄 갱신.

    학습(learn) 통과 시에도 동일 함수로 next_due_at을 잡을 수 있다(§9).
    interval_factor: 학습 목적 정책(learning.policy)의 주기 계수 —
      <1이면 더 자주(시험), >1이면 느슨하게(교양). ease에는 손대지 않아
      목적을 바꿔도 학습 이력(ease 궤적)은 오염되지 않는다.
    """
    now = now or datetime.now(timezone.utc)
    if score is not None:
        quality = _quality_from_score(score)
    elif correct is not None:
        quality = _quality_from_correct(correct)
    else:
        quality = 2

    if quality < 3:
        new_interval = 1
        new_ease = max(1.3, ease - 0.2)
    else:
        new_ease = _sm2_ease_update(ease, quality)
        if interval_days == 0:
            new_interval = 1
        elif interval_days == 1:
            new_interval = 6
        else:
            new_interval = max(1, round(interval_days * new_ease))

    new_interval = max(1, round(new_interval * interval_factor))
    next_due = now + timedelta(days=new_interval)
    return ReviewSchedule(ease=round(new_ease, 3), interval_days=new_interval, next_due_at=next_due)


def is_due(*, next_due_at: datetime | None, now: datetime | None = None) -> bool:
    if next_due_at is None:
        return False
    now = now or datetime.now(timezone.utc)
    if next_due_at.tzinfo is None:
        next_due_at = next_due_at.replace(tzinfo=timezone.utc)
    return next_due_at <= now
