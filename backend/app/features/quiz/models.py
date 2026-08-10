"""[5.Entity] 문제은행 테이블 (docs/QUIZ.md §2-⑦).

quiz_attempts는 학습 attempts와 물리 분리 — 확정안 §7-③ 데이터 격리.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, SmallInteger, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class QuizItem(Base):
    __tablename__ = "quiz_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    toc_index: Mapped[int] = mapped_column(Integer, nullable=False)
    toc_title: Mapped[str] = mapped_column(String, nullable=False, default="")
    type: Mapped[str] = mapped_column(String, nullable=False)
    concept_name: Mapped[str | None] = mapped_column(String)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    difficulty: Mapped[int | None] = mapped_column(SmallInteger)
    # standard | exam — 기출 스타일 배치로 만들어진 문항 표시. 같은 은행에
    # 섞여 있고, "기출만 풀기"는 세션 샘플링이 이 값으로 거른다.
    style: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="standard", default="standard"
    )
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # 인증 붙기 전까지 익명 풀이 허용 → nullable. auth 완성 시 NOT NULL 마이그레이션.
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    quiz_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    correct: Mapped[bool | None] = mapped_column(Boolean)
    user_input: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
