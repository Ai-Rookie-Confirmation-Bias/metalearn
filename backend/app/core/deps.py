"""공통 FastAPI 의존성 — 지금 요청이 누구 것인가.

우선순위가 셋이다:

  1) `Authorization: Bearer <JWT>`  소셜 로그인 토큰(sub=유저 UUID). 정식 경로
  2) `X-User-Id: <UUID>`            로그인 없이 사용자를 지정하는 개발 경로
  3) 둘 다 없으면 고정 dev 유저

**3번이 있는 게 핵심이다.** 로그인을 붙이면서 기존 화면이 전부 401이 되면
데모가 통째로 멈춘다. 토큰이 없으면 지금까지처럼 dev 유저로 돈다.
"""
from __future__ import annotations

import uuid

from fastapi import Header, HTTPException

from app.core.security import decode_access_token

# alembic 0009가 이 id로 users 행을 만들어 둔다. 값이 갈리면 FK가 깨진다.
DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def get_current_user_id(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> uuid.UUID:
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

    if x_user_id is not None:
        try:
            return uuid.UUID(x_user_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="X-User-Id 헤더가 UUID가 아닙니다."
            ) from exc

    return DEV_USER_ID
