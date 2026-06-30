"""[5.Entity] SQLAlchemy DB 테이블 매핑 (벡터 컬럼 포함)."""
from datetime import datetime

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
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


class Curriculum(Base):
    """JIT로 생성된 개념별 브릿지 커리큘럼(인출형 블록 묶음).

    챕터(개념) 진입 시 진단 점수에 따라 구성(선수+메인 / 메인100%)이 결정된다.
    """

    __tablename__ = "curricula"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("diagnostic_sessions.id", ondelete="SET NULL"), nullable=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False, default=settings.BKT_P_INIT)
    # 'focused'(메인100%) | 'bridge'(선수+메인)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="bridge")
    prerequisite_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    main_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    # 인출형 블록 배열 (kind: prose|cloze|inverse, answer 포함).
    blocks: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
