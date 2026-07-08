"""[1.Controller] 성향 프로파일 API.

  GET   /profile/me — 내 성향(축 점수 + 표시 라벨)
  PATCH /profile/me — 축 점수 직접 수정 (측정 오류 시 사용자 안전판)
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.features.profile import repository as repo
from app.features.profile.logic import AXES, profile_label
from app.features.profile.schemas import AxisOut, ProfileOut, ProfileUpdateRequest

router = APIRouter()


def _to_out(axes: dict | None) -> ProfileOut:
    axes = axes or {}
    label, traits = profile_label(axes)
    return ProfileOut(
        axes={
            a: AxisOut(
                score=float((axes.get(a) or {}).get("score", 0.5)),
                confidence=float((axes.get(a) or {}).get("confidence", 0.0)),
                n=int((axes.get(a) or {}).get("n", 0)),
            )
            for a in AXES
        },
        label=label,
        traits=traits,
    )


@router.get("/me", response_model=ProfileOut)
def get_my_profile(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ProfileOut:
    row = repo.get_profile(db, user_id)
    return _to_out(row.axes if row else None)


@router.patch("/me", response_model=ProfileOut)
def update_my_profile(
    body: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ProfileOut:
    events = []
    for axis, score in body.axes.items():
        if axis not in AXES:
            raise HTTPException(status_code=422, detail=f"알 수 없는 축: {axis}")
        if not 0.0 <= score <= 1.0:
            raise HTTPException(status_code=422, detail="점수는 0~1 사이여야 합니다.")
        events.append({"source": "manual", "axis": axis, "signal": score})
    row = repo.append_events(db, user_id=user_id, events=events)
    db.commit()
    return _to_out(row.axes)
