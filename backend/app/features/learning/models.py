"""[Entity] 콘텐츠 봉투 + 학습자 상태 계층.

기획서 §4:
  blocks           — 모든 콘텐츠의 JSON 봉투(검증된 것만 서빙)
  enrollments      — 사람×코스 수강/진단 상태(천장·바닥)
  concept_mastery  — 사람×개념 숙련도 + 복습 스케줄(SM-2)
  attempts         — 모든 시도(append-only, 진단 포함)
  section_progress — 사람×절 진행 상태
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Block(Base):
    """컴포넌트 = JSON 봉투. type으로 프론트 렌더러를 고르고 data만 채운다."""

    __tablename__ = "blocks"
    __table_args__ = (
        Index("ix_blocks_section_order", "section_id", "order_index"),
        Index("ix_blocks_concept_kind", "concept_id", "kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # 진단 블록은 절에 안 묶이므로 nullable
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sections.id", ondelete="CASCADE"), nullable=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # 'concept','mcq','cloze','explainBack','diagnostic'... (자유 확장)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    # diagnostic | learn | review | connection
    kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    concept_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=True
    )
    # book | ai_prereq | analogy
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    tracked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    # ── 근거(출처별) + 검증 ──
    source_chunk_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default="{}"
    )
    external_ref_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default="{}"
    )
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class Enrollment(Base):
    __tablename__ = "enrollments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id"), primary_key=True
    )
    ceiling_concept: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=True
    )
    floor_concept: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=True
    )
    floor_found: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # not_started | in_progress | completed
    diag_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="not_started"
    )
    diag_q_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    self_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ConceptMastery(Base):
    __tablename__ = "concept_mastery"
    __table_args__ = (Index("ix_concept_mastery_due", "user_id", "next_due_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concepts.id"), primary_key=True
    )
    # locked | todo | learning | mastered
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="locked")
    strength: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")
    explanation_score: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0"
    )
    # sure | ambiguous | unknown
    confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ease: Mapped[float] = mapped_column(Float, nullable=False, server_default="2.5")
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Attempt(Base):
    """모든 시도(append-only). 진단/학습/복습/연결 공통 기록."""

    __tablename__ = "attempts"
    __table_args__ = (
        Index("ix_attempts_user_concept_time", "user_id", "concept_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    block_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("blocks.id"), nullable=True
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=False
    )
    # diagnostic | learn | review | connection
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    # 서술형/탐색형은 null
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    user_input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    feedback: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SectionProgress(Base):
    __tablename__ = "section_progress"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sections.id"), primary_key=True
    )
    # not_started | in_progress | completed
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="not_started"
    )
    # full | compressed | quick
    variant_served: Mapped[str | None] = mapped_column(String(32), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
