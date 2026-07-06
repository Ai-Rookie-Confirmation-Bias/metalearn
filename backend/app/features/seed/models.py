"""[Entity] 씨앗(개념 그래프) 계층.

기획서 §4 A. 개념 그래프:
  courses       — 문서 1건으로 만든 코스(개념들의 컨테이너)
  concepts      — 개념 노드(학습·추적·생성의 핵심 단위)
  external_refs — 책에 없는 선행(ai_prereq) 개념의 외부 신뢰 근거
  concept_edges — 개념 간 방향 관계(선행/연관/응용)
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    concepts: Mapped[list["Concept"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )


class Concept(Base):
    __tablename__ = "concepts"
    __table_args__ = (UniqueConstraint("course_id", "key", name="uq_concepts_course_key"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # book | ai_prereq  (개념 출처. 근거 내용은 blocks/external_refs에 붙음)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    depth_level: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    course: Mapped["Course"] = relationship(back_populates="concepts")
    external_refs: Mapped[list["ExternalRef"]] = relationship(
        back_populates="concept", cascade="all, delete-orphan"
    )


class ExternalRef(Base):
    __tablename__ = "external_refs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 'web' | 'corpus' | 'prereq_db'
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    concept: Mapped["Concept"] = relationship(back_populates="external_refs")


class ConceptEdge(Base):
    __tablename__ = "concept_edges"
    __table_args__ = (Index("ix_concept_edges_to", "to_concept_id"),)

    from_concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    to_concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # prerequisite | related | application
    kind: Mapped[str] = mapped_column(String(32), primary_key=True)
