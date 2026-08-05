"""문제은행 테이블 (quiz_items / quiz_attempts) — docs/QUIZ.md §2-⑦.

quiz_attempts는 학습 attempts와 물리 분리 (확정안 §7-③ 데이터 격리).

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quiz_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("toc_index", sa.Integer(), nullable=False),
        sa.Column("toc_title", sa.String(), nullable=False, server_default=""),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("concept_name", sa.String(), nullable=True),
        sa.Column("data", JSONB(), nullable=False),
        sa.Column("evidence", JSONB(), nullable=False),
        sa.Column("difficulty", sa.SmallInteger(), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_quiz_items_scope", "quiz_items", ["course_id", "document_id", "toc_index"]
    )

    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("quiz_item_id", sa.Uuid(), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=True),
        sa.Column("user_input", JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_quiz_attempts_user", "quiz_attempts", ["user_id"])


def downgrade() -> None:
    op.drop_table("quiz_attempts")
    op.drop_table("quiz_items")
