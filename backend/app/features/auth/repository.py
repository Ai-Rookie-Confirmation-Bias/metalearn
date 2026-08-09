"""사용자 DB 접근 — 소셜 계정 find-or-create."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.auth.models import User


class AuthRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_or_create_oauth_user(
        self, *, provider: str, provider_sub: str, email: str, name: str | None
    ) -> User:
        """소셜 계정 find-or-create.

        ① (provider, provider_sub)로 기존 소셜 계정을 찾는다.
        ② 없으면 같은 email의 계정에 소셜 정보를 연결한다 — 구글로 가입한 사람이
           네이버로 다시 들어와도 계정이 둘로 갈라지지 않는다.
        ③ 그래도 없으면 신규 생성.
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
