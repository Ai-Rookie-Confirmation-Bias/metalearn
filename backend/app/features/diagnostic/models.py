"""[5.Entity] 정밀 진단(BKT) 도메인 테이블.

개념(Concept) 단위로 숙련 확률을 추적한다.
  DiagnosticSession 1 ── N ConceptMastery   (개념별 BKT 상태)
  DiagnosticSession 1 ── N DiagnosticQuestion (생성·응답된 퀴즈)
"""
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DiagnosticSession(Base):
    """한 자료(Material)에 대한 진단 세션. 'active' → 'completed'."""

    __tablename__ = "diagnostic_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    masteries: Mapped[list["ConceptMastery"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ConceptMastery(Base):
    """세션×개념 BKT 상태. p_known이 경계(>=high/<=low)에 닿으면 resolved."""

    __tablename__ = "concept_masteries"
    __table_args__ = (
        UniqueConstraint("session_id", "concept_id", name="uq_mastery_session_concept"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("diagnostic_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    p_known: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    answered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 게이티드 진단: 잠긴(locked) 개념은 출제 대상에서 제외.
    # 메인(최상위) 개념은 unlocked, 하위(선수) 개념은 locked로 시작하며
    # 상위 개념을 오답하면 그때 직접 하위만 잠금 해제된다.
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    session: Mapped["DiagnosticSession"] = relationship(back_populates="masteries")


class DiagnosticQuestion(Base):
    """생성된 진단 문항(mcq/cloze/inverse). 정답·근거는 채점 후에만 노출.

    유형별 채워지는 필드:
      mcq      → options, answer_index
      cloze    → expected_answer, acceptable_answers
      inverse  → expected_answer
    """

    __tablename__ = "diagnostic_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("diagnostic_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    qtype: Mapped[str] = mapped_column(String(16), nullable=False, default="mcq")
    question: Mapped[str] = mapped_column(Text, nullable=False)
    # mcq 전용
    options: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    answer_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # cloze/inverse 전용
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    acceptable_answers: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 풀에서 현재 출제 중인 문항 표시 (배치 생성 후 1개만 True).
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 응답
    answered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    selected_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
