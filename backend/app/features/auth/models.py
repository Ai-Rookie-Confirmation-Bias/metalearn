"""[Entity] 사용자 계정. 모든 학습자 계층 데이터의 루트 외래키."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    # 소셜 계정 유일성: 같은 provider 안에서 provider_sub(제공자측 고유 id)는 하나.
    __table_args__ = (
        UniqueConstraint("provider", "provider_sub", name="uq_users_provider_sub"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    # 소셜 로그인 사용자는 비밀번호가 없다 → nullable (OAuth 도입, 마이그 0017).
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 인증 출처: 'local'(이메일/비번) | 'google' | 'naver'. 기본 local(하위호환).
    provider: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="local"
    )
    # 제공자측 사용자 고유 id(구글 sub, 네이버 id). local 사용자는 NULL.
    provider_sub: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 표시 이름(소셜 프로필). 선택.
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
