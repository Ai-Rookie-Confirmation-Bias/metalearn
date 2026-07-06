"""공통 FastAPI 의존성.

인증(auth feature)이 완성되기 전까지의 임시 유저 식별:
  - `X-User-Id` 헤더에 UUID가 오면 그 유저로 동작
  - 없으면 고정 dev 유저 UUID (00000000-...-0001)
auth 구현 후 JWT 기반 get_current_user 로 교체한다(시그니처 동일 유지).
"""
from __future__ import annotations

import uuid

from fastapi import Header, HTTPException

DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def get_current_user_id(x_user_id: str | None = Header(default=None)) -> uuid.UUID:
    if x_user_id is None:
        return DEV_USER_ID
    try:
        return uuid.UUID(x_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid X-User-Id header") from exc
