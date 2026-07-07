"""[Entity] 진단(BKT) 세션·문항 — UUID 포팅(병합 2단계).

parsing이 재정의했던 Enrollment/ConceptMastery는 삭제하고 정본
(features/learning/models.py)을 소비한다. 진단이 세션 단위로 쓰는
숙련도 작업 상태(session_id/answered_count/resolved/locked)는
learning.ConceptMastery에 흡수됨.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DiagnosticSession(Base):
    """코스당 진단 실행 세션(문항·숙련도 풀)."""

    __tablename__ = "diagnostic_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # active | completed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    # 'full' = 기존 전수/스코핑 진단, 'placement' = 배치고사(depth 하강, ISSUE-015)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, server_default="full")
    # 배치고사 진행 상태(모드·현재 개념·응답 이력) — placement 세션만 사용
    state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class DiagnosticQuestion(Base):
    __tablename__ = "diagnostic_questions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("diagnostic_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # mcq | cloze | inverse
    qtype: Mapped[str] = mapped_column(String(16), nullable=False, default="mcq")
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    answer_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    acceptable_answers: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    answered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    selected_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
