"""[Entity] 학습자 성향 프로파일 (진단 재설계 — disposition profiling).

성향축은 과목 무관·사용자 단위(브리프 §2.1 "거의 고정")라서 코스 스코프
(enrollments)가 아닌 사용자 레벨 테이블로 둔다. 축은 연속 점수 + 신뢰도 —
유형 라벨로 굳히면 측정 오차가 영구화되므로 라벨은 표시용 파생값으로만 쓴다.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LearnerProfile(Base):
    __tablename__ = "learner_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    # {"representation": {"score": 0.72, "confidence": 0.45, "n": 3}, ...}
    axes: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    # 측정 이벤트 로그(append-only) [{at, source, axis, signal}] — 감사·재계산용
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
