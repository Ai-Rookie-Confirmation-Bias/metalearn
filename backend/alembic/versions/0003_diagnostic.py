"""diagnostic_sessions/concept_masteries/diagnostic_questions 생성 (BKT 진단 도메인).

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "diagnostic_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_diagnostic_sessions_material_id", "diagnostic_sessions", ["material_id"]
    )

    op.create_table(
        "concept_masteries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("concept_id", sa.Integer(), nullable=False),
        sa.Column("p_known", sa.Float(), nullable=False, server_default="0.3"),
        sa.Column("answered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(
            ["session_id"], ["diagnostic_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_id", "concept_id", name="uq_mastery_session_concept"),
    )
    op.create_index("ix_concept_masteries_session_id", "concept_masteries", ["session_id"])
    op.create_index("ix_concept_masteries_concept_id", "concept_masteries", ["concept_id"])

    op.create_table(
        "diagnostic_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("concept_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("answer_index", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False, server_default=""),
        sa.Column("answered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("selected_index", sa.Integer(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["diagnostic_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_diagnostic_questions_session_id", "diagnostic_questions", ["session_id"]
    )
    op.create_index(
        "ix_diagnostic_questions_concept_id", "diagnostic_questions", ["concept_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_diagnostic_questions_concept_id", table_name="diagnostic_questions"
    )
    op.drop_index(
        "ix_diagnostic_questions_session_id", table_name="diagnostic_questions"
    )
    op.drop_table("diagnostic_questions")
    op.drop_index("ix_concept_masteries_concept_id", table_name="concept_masteries")
    op.drop_index("ix_concept_masteries_session_id", table_name="concept_masteries")
    op.drop_table("concept_masteries")
    op.drop_index(
        "ix_diagnostic_sessions_material_id", table_name="diagnostic_sessions"
    )
    op.drop_table("diagnostic_sessions")
