"""사용자 DB 접근 — dev 유저 조회 + 소셜 계정 find-or-create."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import DEV_USER_ID
from app.features.auth.models import User

_DEV_EMAIL = "dev@local"


class AuthRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_or_create_dev_user(self) -> User:
        """로그인 전 경로가 보는 고정 유저.

        alembic 0009가 이미 넣어 두지만, 볼륨을 지우고 마이그레이션 없이 뜨는
        경우까지 서버가 죽지 않도록 여기서도 없으면 만든다. 비밀번호는 없다 —
        이 계정으로 로그인하는 문이 없다.
        """
        user = self.db.get(User, DEV_USER_ID)
        if user is not None:
            return user
        user = User(id=DEV_USER_ID, email=_DEV_EMAIL, provider="local")
        self.db.add(user)
        self.db.flush()
        return user

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
