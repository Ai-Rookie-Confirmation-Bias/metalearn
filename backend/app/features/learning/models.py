"""[5.Entity] SQLAlchemy DB 테이블 매핑 (벡터 컬럼 포함)."""
from datetime import datetime

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LearningItem(Base):
    __tablename__ = "learning_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[str] = mapped_column(String, nullable=False)
    # 임베딩: Solar embedding 차원에 맞춰 조정 (예시 4096)
    embedding: Mapped[list[float] | None] = mapped_column(HALFVEC(4096), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
