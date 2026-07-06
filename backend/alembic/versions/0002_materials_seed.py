"""documents, chunks, seed profiles, diagnostics

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import HALFVEC
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.Column("page_count", sa.Integer(), server_default="0"),
        sa.Column("parse_status", sa.String(32), server_default="pending"),
        sa.Column("skeleton", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", HALFVEC(4096), nullable=True),
    )

    op.create_table(
        "learning_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("embedding", HALFVEC(4096), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "seed_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("learning_range", postgresql.JSONB(), nullable=False),
        sa.Column("known_before", postgresql.JSONB(), server_default="[]"),
        sa.Column("learning_goal", sa.String(64), nullable=True),
        sa.Column("concepts_in_range", postgresql.JSONB(), server_default="[]"),
        sa.Column("weaknesses", postgresql.JSONB(), server_default="[]"),
        sa.Column("status", sa.String(32), server_default="survey_done"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "diagnostic_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("seed_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), server_default="in_progress"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "diagnostic_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("diagnostic_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("concept_id", sa.String(64), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=False),
        sa.Column("correct_index", sa.Integer(), nullable=False),
        sa.Column("source_chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.create_table(
        "diagnostic_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("diagnostic_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_choice_index", sa.Integer(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("diagnostic_answers")
    op.drop_table("diagnostic_questions")
    op.drop_table("diagnostic_sessions")
    op.drop_table("seed_profiles")
    op.drop_table("learning_items")
    op.drop_table("document_chunks")
    op.drop_table("documents")
