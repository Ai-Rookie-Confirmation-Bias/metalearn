"""[Entity] 사용자 계정. 학습자 계층 데이터의 루트다.

이 테이블이 없어서 `courses.user_id`와 `user_documents.user_id`가 FK 없이
떠 있었다(docs/STATUS.md §5). alembic 0009가 만들면서 둘 다 연결했다.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    # 같은 provider 안에서 provider_sub(제공자측 고유 id)는 하나.
    # Postgres는 NULL을 서로 다르게 취급하므로 local 사용자끼리는 안 부딪힌다.
    __table_args__ = (
        UniqueConstraint("provider", "provider_sub", name="uq_users_provider_sub"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    # 소셜 로그인 사용자는 비밀번호가 없다.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 인증 출처: 'local' | 'google' | 'naver'
    provider: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="local"
    )
    # 제공자측 사용자 고유 id(구글 sub, 네이버 id). local 사용자는 NULL.
    provider_sub: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
