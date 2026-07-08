"""공통 FastAPI 의존성 — 현재 사용자 식별.

우선순위:
  1) `Authorization: Bearer <JWT>` — OAuth 로그인 토큰(sub=유저 UUID). 정식 경로.
  2) `X-User-Id: <UUID>` 헤더 — 인증 UI 전 임시/개발 경로(하위호환).
  3) 둘 다 없으면 고정 dev 유저 UUID (00000000-...-0001).
"""
from __future__ import annotations

import uuid

from fastapi import Header, HTTPException

from app.core.security import decode_access_token

DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def get_current_user_id(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> uuid.UUID:
    # 1) Bearer JWT (OAuth 로그인)
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        sub = decode_access_token(token)
        if sub is None:
            raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
        try:
            return uuid.UUID(sub)
        except ValueError as exc:
            raise HTTPException(
                status_code=401, detail="토큰 주체가 올바르지 않습니다."
            ) from exc

    # 2) X-User-Id (임시/개발)
    if x_user_id is not None:
        try:
            return uuid.UUID(x_user_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="invalid X-User-Id header"
            ) from exc

    # 3) 기본 dev 유저
    return DEV_USER_ID
