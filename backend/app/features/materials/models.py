"""[Entity] 업로드 문서 + RAG 청크.

기획서 §4 A. 콘텐츠 계층:
  documents  — 업로드된 PDF 한 건
  doc_chunks — 파싱 마크다운을 잘게 나눈 RAG 검색/검증 근거 창고
"""
import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import DateTime, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
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
    # 병합(parsing): 섭취 파이프라인은 스토리지 없이 원문만 저장하므로 nullable로 완화.
    storage_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 병합(parsing, ISSUE-014): 정제된 elements = 운영용 원본({"scan":…, "elements":[…]}).
    # raw_text는 보존용. 제거 대상은 삭제 대신 removed 마킹, 파트 경계는 part 필드.
    refined_elements: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # 병합(parsing): 문서 성격 라벨 linked(연결형)|enumerative(나열형)|mixed. v1은 저장만.
    profile: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # 병합(parsing): 섭취 실패 사유 기록.
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty_est: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # 다중 PDF 통합(1:N): 코스가 문서 N개를 순서대로 소유. 문서는 course 생성
    # 후 연결되므로 nullable. seq = 코스 내 학습 순서, role = primary(교재 척추,
    # 트리에 포함) | supplementary(RAG 근거로만, 트리 제외).
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="primary"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="processing"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chunks: Mapped[list["DocChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    # 병합(parsing): 코스 조회 시 문서 메타(filename/status) 접근용.
    courses: Mapped[list["Course"]] = relationship(  # noqa: F821 — seed.models.Course
        "Course", back_populates="document", cascade="all, delete-orphan",
        foreign_keys="Course.document_id",
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
    # 병합(parsing): 청킹 메타 — element_from/to는 refined_elements 배열의 요소 번호
    # 범위(드릴다운 좌표), heading은 대표 헤딩 경로, part_index는 정제 스캔의 파트
    # 번호. 마크다운 폴백 청킹에서는 요소 좌표가 없어 NULL.
    element_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    element_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    part_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_to: Mapped[int | None] = mapped_column(Integer, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="chunks")
