"""[5.Entity] 콘텐츠 + 개념 그래프 (팀 스키마: users → documents → courses → concepts)."""
from datetime import datetime

from typing import Any

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.database import Base


class Document(Base):
    """업로드 PDF 파싱 결과(원문 텍스트)."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 정제 v1 (ISSUE-014): 정제된 elements = 운영용 원본. raw_text는 보존용.
    # 제거 대상은 삭제 대신 removed 마킹, 파트 경계는 part 필드로 표시.
    refined_elements: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB, nullable=True
    )
    # 문서 성격 라벨: linked(연결형)|enumerative(나열형)|mixed. v1은 저장만.
    profile: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="processing")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    courses: Mapped[list["Course"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocChunk(Base):
    """RAG 문서 청크 (팀 스키마 doc_chunks 정렬) — 추출·생성의 원문 근거 단위.

    element_from/to는 refined_elements 배열의 요소 번호 범위 — 필요 시 더
    깊은 원본(요소 좌표·페이지)으로 드릴다운하는 정밀 주소. 마크다운 폴백
    청킹에서는 요소 좌표가 없어 NULL.
    """

    __tablename__ = "doc_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        HALFVEC(settings.SOLAR_EMBED_DIM), nullable=True
    )
    element_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    element_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    part_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_to: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Course(Base):
    """문서 기반 학습 코스(개념·진단의 부모 단위)."""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    category: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    document: Mapped["Document"] = relationship(back_populates="courses")
    concepts: Mapped[list["Concept"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )


class Concept(Base):
    __tablename__ = "concepts"
    __table_args__ = (UniqueConstraint("course_id", "name", name="uq_concept_course_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    # 계약(ii.md): 코스 내 유니크 영문 슬러그 — 커리큘럼 생성 프롬프트 키.
    key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    depth_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 출처: 'document' = 교재에서 직접 추출, 'llm' = LLM이 보충한 선수개념.
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="document")
    # 교재 추출 개념의 원문 섹션(헤딩 경로) — 사람이 읽는 표시용.
    source_anchor: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 원문 청크 FK — JIT/문제 근거 주입 시 원문 조회 키 (anchor 문자열의 정밀판).
    source_chunk_id: Mapped[int | None] = mapped_column(
        ForeignKey("doc_chunks.id", ondelete="SET NULL"), nullable=True
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        HALFVEC(settings.SOLAR_EMBED_DIM), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    course: Mapped["Course"] = relationship(back_populates="concepts")
    prerequisite_edges: Mapped[list["ConceptEdge"]] = relationship(
        back_populates="concept",
        foreign_keys="ConceptEdge.from_concept_id",
        cascade="all, delete-orphan",
    )


class Chapter(Base):
    """커리큘럼 챕터(장) — 씨앗이 생성, gen_status 전이는 커리큘럼 파트 소관 (ii.md)."""

    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(String(16), nullable=False, default="book")
    gen_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")


class Section(Base):
    """커리큘럼 절 — 절 ↔ 대표 개념 1:1 (concept_id 없으면 생성기가 스킵)."""

    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concept_id: Mapped[int | None] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)


class ConceptEdge(Base):
    __tablename__ = "concept_edges"
    __table_args__ = (
        UniqueConstraint(
            "from_concept_id", "to_concept_id", "kind", name="uq_concept_edge"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    to_concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="prerequisite")

    concept: Mapped["Concept"] = relationship(
        back_populates="prerequisite_edges", foreign_keys=[from_concept_id]
    )
