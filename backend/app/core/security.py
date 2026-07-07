"""JWT 발급/검증 및 패스워드 해싱 (스텁 — auth 구현 시 사용).

해싱은 bcrypt를 직접 호출한다(병합 v2 수정): passlib 1.7.4는 bcrypt 4.1+의
`__about__` 제거로 버전 탐지가 깨져 해싱 자체가 실패한다(환경 의존 500).
bcrypt는 72바이트 초과 입력을 거부하므로 미리 절단한다.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from app.core.config import settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


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
