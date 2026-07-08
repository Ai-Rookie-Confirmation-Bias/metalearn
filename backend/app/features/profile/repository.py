"""[4.Repository] 학습자 성향 프로파일 DB 접근."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.features.profile.logic import compute_axes
from app.features.profile.models import LearnerProfile


def get_profile(db: Session, user_id: uuid.UUID) -> LearnerProfile | None:
    return db.get(LearnerProfile, user_id)


def get_axes(db: Session, user_id: uuid.UUID) -> dict | None:
    """생성 파이프라인용 얇은 조회 — 프로파일 없으면 None(중립 생성)."""
    row = db.get(LearnerProfile, user_id)
    return dict(row.axes or {}) if row is not None else None


def append_events(
    db: Session, *, user_id: uuid.UUID, events: list[dict]
) -> LearnerProfile:
    """측정 이벤트 append + 축 상태 재계산(단일 진실 = evidence 로그)."""
    row = db.get(LearnerProfile, user_id)
    if row is None:
        row = LearnerProfile(user_id=user_id, axes={}, evidence=[])
        db.add(row)
    now = datetime.now(timezone.utc).isoformat()
    stamped = [{"at": now, **e} for e in events]
    merged = [*(row.evidence or []), *stamped]
    row.evidence = merged  # 재할당으로 JSONB 변경 감지
    row.axes = compute_axes(merged)
    db.flush()
    return row
