"""[Entity] 커리큘럼 계층(학습 경로 뼈대).

기획서 §4 A:
  chapters — 학습 큰 단위. JIT 생성 트리거(gen_status)를 가짐. 사람마다 다르게 구성됨.
  sections — 절(개념과 1:1 매핑되는 학습·추적 단위).

concepts(지식 지도, 불변)와 달리 chapters/sections는 진단 결과로 사람마다 생성된다.
"""
import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    # book | prereq  (동적 삽입된 선행 챕터는 prereq)
    origin: Mapped[str] = mapped_column(String(32), nullable=False, server_default="book")
    # pending | generating | ready | failed  (JIT 생성 트리거)
    gen_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="pending"
    )

    sections: Mapped[list["Section"]] = relationship(
        back_populates="chapter", cascade="all, delete-orphan"
    )


class Section(Base):
    __tablename__ = "sections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    concept_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)

    chapter: Mapped["Chapter"] = relationship(back_populates="sections")
