"""[Entity] 씨앗(개념 그래프) 계층.

기획서 §4 A. 개념 그래프:
  courses       — 문서 1건으로 만든 코스(개념들의 컨테이너)
  concepts      — 개념 노드(학습·추적·생성의 핵심 단위)
  external_refs — 책에 없는 선행(ai_prereq) 개념의 외부 신뢰 근거
  concept_edges — 개념 간 방향 관계(선행/연관/응용)
"""
import uuid
from datetime import datetime

from pgvector.sqlalchemy import HALFVEC
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
from app.features.materials.models import EMBED_DIM


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
    # 병합(parsing): 코스 목록/상세에서 문서 메타(filename/status) 접근용.
    document: Mapped["Document"] = relationship(  # noqa: F821 — materials.models.Document
        "Document", back_populates="courses"
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
    # 코스 내 유니크 영문 슬러그 — 커리큘럼 생성 프롬프트 키.
    # TODO(병합, ISSUE-001): parsing 섭취는 추출 시점에 key가 없고 씨앗 조립
    # (seed/service._fill_keys)에서 채운다 → 잠정 nullable. 팀 합의 후
    # NOT NULL 복원(MERGE_AGREEMENT: NOT NULL + UNIQUE(course_id, key)).
    key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # book | ai_prereq  (개념 출처. 근거 내용은 blocks/external_refs에 붙음)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    depth_level: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # 병합(parsing): 교재 추출 개념의 원문 섹션(헤딩 경로) — 사람이 읽는 표시용.
    source_anchor: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 병합(parsing): 원문 청크 FK — 문항/JIT 근거 주입 시 원문 조회 키.
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doc_chunks.id", ondelete="SET NULL"), nullable=True
    )
    # 병합(parsing, ISSUE-015): 상류가 저장한 개념 임베딩(query 모델) — 하류는
    # 재임베딩 없이 소비. doc_chunks.embedding(passage)과 비대칭 쌍.
    embedding: Mapped[list[float] | None] = mapped_column(
        HALFVEC(EMBED_DIM), nullable=True
    )
    # 병합(parsing): 생성 시각 (섭취 파이프라인 진행 로그·정렬 보조).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    course: Mapped["Course"] = relationship(back_populates="concepts")
    external_refs: Mapped[list["ExternalRef"]] = relationship(
        back_populates="concept", cascade="all, delete-orphan"
    )
    # 병합(parsing): 이 개념이 from(의존)인 에지 목록 — 선수 id 조회용
    # (그래프 방향 규약: from=의존 → to=선수, GRAPH_ORIENTATION_CONTRACT).
    prerequisite_edges: Mapped[list["ConceptEdge"]] = relationship(
        "ConceptEdge",
        foreign_keys="ConceptEdge.from_concept_id",
        cascade="all, delete-orphan",
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
