"""[5.Entity] 학습 자료 섭취(Ingestion) 도메인 테이블.

데이터는 항상 '개념(Concept)' 단위로 추적된다:
  Material(원본 PDF) 1 ── N Concept(파편화된 개념)
  Concept N ── N Concept  (선수지식 그래프, ConceptPrerequisite 엣지)
"""
from datetime import datetime

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.database import Base


class Material(Base):
    """업로드된 원본 자료 1건 + 파싱된 마크다운."""

    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    # 'parsing' → 'extracting' → 'ready' / 'failed'
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="parsing")
    markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    concepts: Mapped[list["Concept"]] = relationship(
        back_populates="material",
        cascade="all, delete-orphan",
    )


class Concept(Base):
    """파편화된 개념 노드. JIT 라우팅/BKT 추적의 최소 단위."""

    __tablename__ = "concepts"
    __table_args__ = (UniqueConstraint("material_id", "name", name="uq_concept_material_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # 추출 트리에서의 깊이 (0 = 타겟 루트). N-2 상한은 추출 스키마에서 강제.
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding: Mapped[list[float] | None] = mapped_column(
        HALFVEC(settings.SOLAR_EMBED_DIM), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    material: Mapped["Material"] = relationship(back_populates="concepts")

    # 이 개념이 '의존하는' 선수 개념 엣지들 (concept → prerequisite).
    prerequisite_edges: Mapped[list["ConceptPrerequisite"]] = relationship(
        back_populates="concept",
        foreign_keys="ConceptPrerequisite.concept_id",
        cascade="all, delete-orphan",
    )


class ConceptPrerequisite(Base):
    """방향성 선수지식 엣지: concept_id 는 prerequisite_concept_id 를 선행 요구한다.

    전체 선행 그래프(길)를 미리 깔아두기 위한 인접 테이블.
    """

    __tablename__ = "concept_prerequisites"
    __table_args__ = (
        UniqueConstraint(
            "concept_id", "prerequisite_concept_id", name="uq_concept_prereq_edge"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prerequisite_concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    concept: Mapped["Concept"] = relationship(
        back_populates="prerequisite_edges", foreign_keys=[concept_id]
    )
