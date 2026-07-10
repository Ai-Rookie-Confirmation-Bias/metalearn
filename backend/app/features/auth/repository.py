"""사용자 DB 접근. 기본 개발 사용자 + OAuth 소셜 계정 find-or-create."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import DEV_USER_ID
from app.core.security import hash_password
from app.features.auth.models import User

_DEFAULT_EMAIL = "dev@local"
_DEFAULT_PASSWORD = "dev"


class AuthRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_default_user(self) -> User:
        """로그인 전 MVP: 단일 개발 사용자를 반환(없으면 생성).

        병합 v2 수정: parsing 파이프라인(seed/enrollment)과 학습·프론트
        (get_current_user_id 기본값·X-User-Id)가 같은 유저를 보도록 고정
        DEV_USER_ID(00000000-...-0001)로 통일한다. 이전엔 랜덤 UUID라
        seed가 만든 enrollment를 커리큘럼이 못 찾았다(enrollment not found).
        """
        user = self.db.get(User, DEV_USER_ID)
        if user is not None:
            return user
        user = User(
            id=DEV_USER_ID,
            email=_DEFAULT_EMAIL,
            password_hash=hash_password(_DEFAULT_PASSWORD),
        )
        self.db.add(user)
        self.db.flush()
        return user

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_or_create_oauth_user(
        self, *, provider: str, provider_sub: str, email: str, name: str | None
    ) -> User:
        """소셜 계정 find-or-create.

        ① (provider, provider_sub)로 기존 소셜 계정을 찾는다.
        ② 없으면 같은 email의 기존 계정에 소셜 정보를 연결(중복 가입 방지).
        ③ 그래도 없으면 신규 생성(password_hash=None).
        """
        user = self.db.scalars(
            select(User).where(
                User.provider == provider, User.provider_sub == provider_sub
            )
        ).first()
        if user is not None:
            if name and user.name != name:
                user.name = name
            return user

        existing = self.db.scalars(select(User).where(User.email == email)).first()
        if existing is not None:
            existing.provider = provider
            existing.provider_sub = provider_sub
            if name:
                existing.name = name
            self.db.flush()
            return existing

        user = User(
            email=email,
            provider=provider,
            provider_sub=provider_sub,
            name=name,
            password_hash=None,
        )
        self.db.add(user)
        self.db.flush()
        return user
