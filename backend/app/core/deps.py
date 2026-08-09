"""공통 FastAPI 의존성 — 지금 요청이 누구 것인가.

우선순위가 셋이다:

  1) `Authorization: Bearer <JWT>`  소셜 로그인 토큰(sub=유저 UUID). 정식 경로
  2) `X-User-Id: <UUID>`            로그인 없이 사용자를 지정하는 개발 경로
  3) 둘 다 없으면 고정 dev 유저

**3번이 있는 게 핵심이다.** 로그인을 붙이면서 기존 화면이 전부 401이 되면
데모가 통째로 멈춘다. 토큰이 없으면 지금까지처럼 dev 유저로 돈다.

정한 주체는 **실재하는 계정이어야 한다.** users에 없는 id를 통과시키면 읽기는
멀쩡히 되는데 소유를 남기는 순간 FK가 터진다 — 업로드가 500으로 죽고 원인은
로그에만 남는다(실측). 여기서 한 번 막으면 쓰는 자리마다 안 막아도 된다.
"""
from __future__ import annotations

import uuid

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.features.auth.models import User

# alembic 0009가 이 id로 users 행을 만들어 둔다. 값이 갈리면 FK가 깨진다.
DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_DEV_EMAIL = "dev@local"


def get_current_user_id(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> uuid.UUID:
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        sub = decode_access_token(token)
        if sub is None:
            raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
        try:
            user_id = uuid.UUID(sub)
        except ValueError as exc:
            raise HTTPException(
                status_code=401, detail="토큰 주체가 올바르지 않습니다."
            ) from exc
        if db.get(User, user_id) is None:
            # 계정이 지워졌는데 토큰만 남은 경우. 401이라야 프론트가 토큰을
            # 비우고 dev 폴백으로 내려간다(client.ts 응답 인터셉터).
            raise HTTPException(status_code=401, detail="계정을 찾을 수 없습니다.")
        return user_id

    if x_user_id is not None:
        try:
            user_id = uuid.UUID(x_user_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="X-User-Id 헤더가 UUID가 아닙니다."
            ) from exc
        if user_id != DEV_USER_ID and db.get(User, user_id) is None:
            raise HTTPException(
                status_code=400, detail="X-User-Id가 존재하지 않는 계정입니다."
            )
        if user_id != DEV_USER_ID:
            return user_id

    return ensure_dev_user(db)


def ensure_dev_user(db: Session) -> uuid.UUID:
    """로그인 전 경로가 보는 고정 유저. 없으면 만든다.

    alembic 0009가 넣어 두지만, 볼륨을 지우고 마이그레이션 없이 뜨는 경우까지
    첫 요청이 죽지 않게 한다.
    """
    if db.get(User, DEV_USER_ID) is None:
        db.add(User(id=DEV_USER_ID, email=_DEV_EMAIL, provider="local"))
        db.commit()
    return DEV_USER_ID
