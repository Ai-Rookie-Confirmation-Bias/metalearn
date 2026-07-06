"""[Entity] 업로드 문서 + RAG 청크.

기획서 §4 A. 콘텐츠 계층:
  documents  — 업로드된 PDF 한 건
  doc_chunks — 파싱 마크다운을 잘게 나눈 RAG 검색/검증 근거 창고
"""
import uuid
from datetime import datetime

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import DateTime, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# 실제 임베딩 차원은 Solar 임베딩 출력(4096)에 맞춘다.
# (기획서의 vector(1536)은 예시값 — 확정값은 4096, HALFVEC 사용.)
EMBED_DIM = 4096


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty_est: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="processing"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chunks: Mapped[list["DocChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocChunk(Base):
    __tablename__ = "doc_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(HALFVEC(EMBED_DIM), nullable=True)
    page_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_to: Mapped[int | None] = mapped_column(Integer, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="chunks")
