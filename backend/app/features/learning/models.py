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
    # 학습 목표(intent): exam | career | culture | hobby (정본 SCHEMA.md)
    purpose: Mapped[str | None] = mapped_column(String(16), nullable=True)
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
    # ── 병합(parsing, 진단 세션 작업 상태) ──────────────────────────
    # 진단(BKT)이 세션 단위로 쓰는 필드. 세션이 끝나면 strength가 씨앗
    # 초기값으로 남고, 학습 서빙은 status/strength만 소비한다.
    # TODO(팀 합의): answered_count는 파생값(원칙② 위반 후보) — 진단이
    # attempts를 기록하게 되면 집계로 대체하고 이 컬럼을 제거한다.
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("diagnostic_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    answered_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    # 진단 확정(경계 도달·문항 소진) 여부
    resolved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    # 게이티드 진단의 출제 잠금(상위 오답 시 해제) — status의 'locked'와 별개
    locked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
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


class LearningCursor(Base):
    """사람×코스 학습 위치 + 복귀 스택(살아있는 커리큘럼 내비게이션).

    선행 삽입으로 우회할 때 원래 절을 return_stack에 쌓고(LIFO, 중첩 선행 대응),
    절 완료 시 pop해 복귀 지점을 정한다. 진행 판정(section_progress)과 별개의 '어디로'.
    """

    __tablename__ = "learning_cursor"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id"), primary_key=True
    )
    current_section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sections.id", ondelete="SET NULL"), nullable=True
    )
    # 복귀 대상 절 id 문자열의 LIFO 스택
    return_stack: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StudyNote(Base):
    """나의 요약 노트 — 절 단위 자기설명 메모(튜터 패널 노트 탭, mig 0021).

    (user, section) 1:1 upsert. section FK CASCADE라 코스 삭제 시 함께 정리.
    """

    __tablename__ = "study_notes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sections.id", ondelete="CASCADE"),
        primary_key=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    updated_at: Mapped[datetime] = mapped_column(
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
