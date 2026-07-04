"""[5.Entity] 콘텐츠 + 개념 그래프 (팀 스키마: users → documents → courses → concepts)."""
from datetime import datetime

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
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
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="processing")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    courses: Mapped[list["Course"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


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
    description: Mapped[str] = mapped_column(Text, nullable=False)
    depth_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 출처: 'document' = 교재에서 직접 추출, 'llm' = LLM이 보충한 선수개념.
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="document")
    # 교재 추출 개념의 원문 섹션(헤딩 경로). JIT 깊이 확장 시 섹션 텍스트 조회 키.
    source_anchor: Mapped[str | None] = mapped_column(Text, nullable=True)
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
