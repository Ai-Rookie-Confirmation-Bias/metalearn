"""파싱 v3 스키마 — 문서·목차·조각·문장·개념·그림.

핵심 설계 (docs/PARSING_v3.md):
  - documents에 user_id가 없다 (공용). 소유는 user_documents로만.
  - doc_segments.topic_id로 조각을 전부 목차에 분류 → 누락이 산술 검산으로 잡힌다.
  - concept_segments가 다대다 → 같은 개념의 여러 원문 출처가 전부 남는다.

임베딩 차원 4096은 실측값이다 (embedding-query / embedding-passage 모두 4096,
2026-08-02 실호출 확인). 바꾸면 저장된 벡터를 전부 재생성해야 한다.

learning_items는 기존 스텁 테이블 — v3 전용 DB(metalearn_v3)를 새로 만들었으므로
여기서 함께 생성한다.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-02
"""
from typing import Sequence, Union

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBED_DIM = 4096


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("source_format", sa.String(length=16), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=True),
        sa.Column("visibility", sa.String(length=16), server_default="private", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("parser_version", sa.String(length=32), server_default="v3.0", nullable=False),
        sa.Column("raw_markdown", sa.Text(), nullable=True),
        sa.Column("refined_elements", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("density_grade", sa.String(length=16), nullable=True),
        sa.Column("avg_segment_chars", sa.Integer(), nullable=True),
        sa.Column("concept_coverage", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_documents_fingerprint"), "documents", ["fingerprint"], unique=True)
    op.create_index(op.f("ix_documents_status"), "documents", ["status"], unique=False)

    op.create_table(
        "user_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        # users 테이블이 아직 없어 FK 미설정. auth 모델이 들어오면 추가할 것.
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=16), server_default="skeleton", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "document_id", name="uq_user_document"),
    )
    op.create_index(op.f("ix_user_documents_document_id"), "user_documents", ["document_id"], unique=False)
    op.create_index(op.f("ix_user_documents_user_id"), "user_documents", ["user_id"], unique=False)

    op.create_table(
        "doc_topics",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("page_from", sa.Integer(), nullable=True),
        sa.Column("page_to", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "seq", name="uq_topic_seq"),
    )
    op.create_index(op.f("ix_doc_topics_document_id"), "doc_topics", ["document_id"], unique=False)

    op.create_table(
        "doc_segments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("topic_id", sa.UUID(), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("heading", sa.Text(), nullable=True),
        sa.Column("element_from", sa.Integer(), nullable=True),
        sa.Column("element_to", sa.Integer(), nullable=True),
        sa.Column("page_from", sa.Integer(), nullable=True),
        sa.Column("page_to", sa.Integer(), nullable=True),
        sa.Column("char_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.HALFVEC(dim=EMBED_DIM), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["doc_topics.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "seq", name="uq_segment_seq"),
    )
    op.create_index(op.f("ix_doc_segments_document_id"), "doc_segments", ["document_id"], unique=False)
    op.create_index(op.f("ix_doc_segments_topic_id"), "doc_segments", ["topic_id"], unique=False)

    op.create_table(
        "segment_sentences",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("segment_id", sa.UUID(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["segment_id"], ["doc_segments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("segment_id", "seq", name="uq_sentence_seq"),
    )
    op.create_index(op.f("ix_segment_sentences_segment_id"), "segment_sentences", ["segment_id"], unique=False)

    op.create_table(
        "concepts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("topic_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("definition", sa.Text(), nullable=True),
        sa.Column("global_key", sa.String(length=128), nullable=True),
        sa.Column("source", sa.String(length=16), server_default="book", nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.HALFVEC(dim=EMBED_DIM), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["doc_topics.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        # 중복 방어 ① — 정규화된 이름은 문서 안에서 유일하다.
        sa.UniqueConstraint("document_id", "normalized_name", name="uq_concept_name"),
    )
    op.create_index(op.f("ix_concepts_document_id"), "concepts", ["document_id"], unique=False)
    op.create_index(op.f("ix_concepts_global_key"), "concepts", ["global_key"], unique=False)
    op.create_index(op.f("ix_concepts_normalized_name"), "concepts", ["normalized_name"], unique=False)
    op.create_index(op.f("ix_concepts_topic_id"), "concepts", ["topic_id"], unique=False)

    # ⭐ 개념 ↔ 조각 다대다. 이 테이블이 v3의 핵심 수정.
    op.create_table(
        "concept_segments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("concept_id", sa.UUID(), nullable=False),
        sa.Column("segment_id", sa.UUID(), nullable=False),
        sa.Column("sentence_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["segment_id"], ["doc_segments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sentence_id"], ["segment_sentences.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("concept_id", "segment_id", name="uq_concept_segment"),
    )
    op.create_index(op.f("ix_concept_segments_concept_id"), "concept_segments", ["concept_id"], unique=False)
    op.create_index(op.f("ix_concept_segments_segment_id"), "concept_segments", ["segment_id"], unique=False)

    op.create_table(
        "concept_edges",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("from_concept_id", sa.UUID(), nullable=False),
        sa.Column("to_concept_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), server_default="prerequisite", nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_concept_id"], ["concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_concept_id"], ["concepts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("from_concept_id", "to_concept_id", "kind", name="uq_concept_edge"),
    )
    op.create_index(op.f("ix_concept_edges_document_id"), "concept_edges", ["document_id"], unique=False)
    op.create_index(op.f("ix_concept_edges_from_concept_id"), "concept_edges", ["from_concept_id"], unique=False)
    op.create_index(op.f("ix_concept_edges_to_concept_id"), "concept_edges", ["to_concept_id"], unique=False)

    op.create_table(
        "doc_figures",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("segment_id", sa.UUID(), nullable=True),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("element_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=32), server_default="figure", nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        # 파싱 단계에서 호출 0회로 준비하는 두 컬럼 (설명 생성은 나중에).
        sa.Column("context_text", sa.Text(), nullable=True),
        sa.Column("needs_vision", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("mime", sa.String(length=64), server_default="image/png", nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["segment_id"], ["doc_segments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_doc_figures_document_id"), "doc_figures", ["document_id"], unique=False)
    op.create_index(op.f("ix_doc_figures_segment_id"), "doc_figures", ["segment_id"], unique=False)

    op.create_table(
        "global_concepts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.HALFVEC(dim=EMBED_DIM), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_global_concepts_key"), "global_concepts", ["key"], unique=True)

    # 기존 스텁 (v3 전용 DB라 여기서 함께 생성)
    op.create_table(
        "learning_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.HALFVEC(dim=EMBED_DIM), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("learning_items")
    op.drop_index(op.f("ix_global_concepts_key"), table_name="global_concepts")
    op.drop_table("global_concepts")
    op.drop_index(op.f("ix_doc_figures_segment_id"), table_name="doc_figures")
    op.drop_index(op.f("ix_doc_figures_document_id"), table_name="doc_figures")
    op.drop_table("doc_figures")
    op.drop_index(op.f("ix_concept_edges_to_concept_id"), table_name="concept_edges")
    op.drop_index(op.f("ix_concept_edges_from_concept_id"), table_name="concept_edges")
    op.drop_index(op.f("ix_concept_edges_document_id"), table_name="concept_edges")
    op.drop_table("concept_edges")
    op.drop_index(op.f("ix_concept_segments_segment_id"), table_name="concept_segments")
    op.drop_index(op.f("ix_concept_segments_concept_id"), table_name="concept_segments")
    op.drop_table("concept_segments")
    op.drop_index(op.f("ix_concepts_topic_id"), table_name="concepts")
    op.drop_index(op.f("ix_concepts_normalized_name"), table_name="concepts")
    op.drop_index(op.f("ix_concepts_global_key"), table_name="concepts")
    op.drop_index(op.f("ix_concepts_document_id"), table_name="concepts")
    op.drop_table("concepts")
    op.drop_index(op.f("ix_segment_sentences_segment_id"), table_name="segment_sentences")
    op.drop_table("segment_sentences")
    op.drop_index(op.f("ix_doc_segments_topic_id"), table_name="doc_segments")
    op.drop_index(op.f("ix_doc_segments_document_id"), table_name="doc_segments")
    op.drop_table("doc_segments")
    op.drop_index(op.f("ix_doc_topics_document_id"), table_name="doc_topics")
    op.drop_table("doc_topics")
    op.drop_index(op.f("ix_user_documents_user_id"), table_name="user_documents")
    op.drop_index(op.f("ix_user_documents_document_id"), table_name="user_documents")
    op.drop_table("user_documents")
    op.drop_index(op.f("ix_documents_status"), table_name="documents")
    op.drop_index(op.f("ix_documents_fingerprint"), table_name="documents")
    op.drop_table("documents")
