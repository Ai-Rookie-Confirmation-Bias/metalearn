"""JWT 발급·검증과 패스워드 해싱.

해싱은 passlib을 거치지 않고 bcrypt를 직접 부른다. passlib 1.7.4가 bcrypt
4.1+에서 버전 탐지에 실패해 **해싱 호출 자체가 죽는다**(feat/oauth-login에서
이미 겪고 고친 자리다). bcrypt는 72바이트 초과 입력을 거부하므로 미리 자른다.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """검증하고 subject를 돌려준다. 만료·서명오류·형식오류면 None."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
    sub = payload.get("sub")
    return str(sub) if sub is not None else None
