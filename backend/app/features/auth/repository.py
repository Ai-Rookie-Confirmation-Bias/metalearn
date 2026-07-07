"""사용자 DB 접근. 인증 UI 전까지 기본 개발 사용자를 제공한다."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.features.auth.models import User

_DEFAULT_EMAIL = "dev@local"
_DEFAULT_PASSWORD = "dev"


class AuthRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_default_user(self) -> User:
        """로그인 전 MVP: 단일 개발 사용자를 반환(없으면 생성)."""
        stmt = select(User).where(User.email == _DEFAULT_EMAIL)
        user = self.db.scalars(stmt).first()
        if user is not None:
            return user
        user = User(email=_DEFAULT_EMAIL, password_hash=hash_password(_DEFAULT_PASSWORD))
        self.db.add(user)
        self.db.flush()
        return user
