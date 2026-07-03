"""blueprint schema — 기획서 §4 기준 전면 재구성 (MVP: 결제/구독/알림 제외)

구 탐색용 테이블(seed_profiles/diagnostic_*/curricula/tutor_* 등)을 정리하고,
users → documents/doc_chunks → courses/concepts/edges/external_refs →
chapters/sections → blocks + 학습자 계층(enrollments/concept_mastery/
attempts/section_progress)을 새로 생성한다.

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import HALFVEC
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBED_DIM = 4096

# 구 스키마(탐색 단계) 테이블 — 전면 교체하므로 드롭.
_OLD_TABLES = [
    "tutor_steps",
    "learning_sessions",
    "curricula",
    "diagnostic_answers",
    "diagnostic_questions",
    "diagnostic_sessions",
    "seed_profiles",
    "learning_items",
    "document_chunks",
    "documents",
]


def _uuid_pk() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def upgrade() -> None:
    # 0) 구 테이블 정리
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")  # gen_random_uuid()
    for table in _OLD_TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')

    # 1) users
    op.create_table(
        "users",
        _uuid_pk(),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 2) documents
    op.create_table(
        "documents",
        _uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("storage_url", sa.String(1024), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("difficulty_est", sa.SmallInteger(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="processing"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_documents_user_id", "documents", ["user_id"])

    # 3) doc_chunks
    op.create_table(
        "doc_chunks",
        _uuid_pk(),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", HALFVEC(EMBED_DIM), nullable=True),
        sa.Column("page_from", sa.Integer(), nullable=True),
        sa.Column("page_to", sa.Integer(), nullable=True),
    )
    op.create_index("ix_doc_chunks_document_id", "doc_chunks", ["document_id"])

    # 4) courses
    op.create_table(
        "courses",
        _uuid_pk(),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("category", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_courses_user_id", "courses", ["user_id"])

    # 5) concepts
    op.create_table(
        "concepts",
        _uuid_pk(),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("depth_level", sa.SmallInteger(), nullable=True),
        sa.UniqueConstraint("course_id", "key", name="uq_concepts_course_key"),
    )
    op.create_index("ix_concepts_course_id", "concepts", ["course_id"])

    # 6) external_refs
    op.create_table(
        "external_refs",
        _uuid_pk(),
        sa.Column("concept_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_external_refs_concept_id", "external_refs", ["concept_id"])

    # 7) concept_edges
    op.create_table(
        "concept_edges",
        sa.Column("from_concept_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("to_concept_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("kind", sa.String(32), primary_key=True),
    )
    op.create_index("ix_concept_edges_to", "concept_edges", ["to_concept_id"])

    # 8) chapters
    op.create_table(
        "chapters",
        _uuid_pk(),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("origin", sa.String(32), nullable=False, server_default="book"),
        sa.Column("gen_status", sa.String(32), nullable=False, server_default="pending"),
    )
    op.create_index("ix_chapters_course_id", "chapters", ["course_id"])

    # 9) sections
    op.create_table(
        "sections",
        _uuid_pk(),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("concept_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("concepts.id"), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
    )
    op.create_index("ix_sections_chapter_id", "sections", ["chapter_id"])

    # 10) blocks
    op.create_table(
        "blocks",
        _uuid_pk(),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sections.id", ondelete="CASCADE"), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=True),
        sa.Column("concept_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("concepts.id"), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("tracked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source_chunk_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default=sa.text("'{}'::uuid[]")),
        sa.Column("external_ref_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default=sa.text("'{}'::uuid[]")),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("meta", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_blocks_section_order", "blocks", ["section_id", "order_index"])
    op.create_index("ix_blocks_concept_kind", "blocks", ["concept_id", "kind"])

    # 11) enrollments
    op.create_table(
        "enrollments",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), primary_key=True),
        sa.Column("ceiling_concept", postgresql.UUID(as_uuid=True), sa.ForeignKey("concepts.id"), nullable=True),
        sa.Column("floor_concept", postgresql.UUID(as_uuid=True), sa.ForeignKey("concepts.id"), nullable=True),
        sa.Column("floor_found", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("diag_status", sa.String(32), nullable=False, server_default="not_started"),
        sa.Column("diag_q_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("self_report", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 12) concept_mastery
    op.create_table(
        "concept_mastery",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("concept_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("concepts.id"), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="locked"),
        sa.Column("strength", sa.Float(), nullable=False, server_default="0"),
        sa.Column("explanation_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.String(32), nullable=True),
        sa.Column("ease", sa.Float(), nullable=False, server_default="2.5"),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_concept_mastery_due", "concept_mastery", ["user_id", "next_due_at"])

    # 13) attempts
    op.create_table(
        "attempts",
        _uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("block_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("blocks.id"), nullable=True),
        sa.Column("concept_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("concepts.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("user_input", postgresql.JSONB(), nullable=True),
        sa.Column("feedback", postgresql.JSONB(), nullable=True),
        sa.Column("meta", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_attempts_user_concept_time", "attempts", ["user_id", "concept_id", "created_at"])

    # 14) section_progress
    op.create_table(
        "section_progress",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sections.id"), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="not_started"),
        sa.Column("variant_served", sa.String(32), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    for table in [
        "section_progress",
        "attempts",
        "concept_mastery",
        "enrollments",
        "blocks",
        "sections",
        "chapters",
        "concept_edges",
        "external_refs",
        "concepts",
        "courses",
        "doc_chunks",
        "documents",
        "users",
    ]:
        op.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
