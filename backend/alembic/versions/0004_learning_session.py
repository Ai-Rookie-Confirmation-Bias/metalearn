"""learning_sessions, tutor_steps

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "learning_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("seed_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("curriculum_unit_order", sa.Integer(), nullable=False),
        sa.Column("concept_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_learning_sessions_profile_id", "learning_sessions", ["profile_id"])

    op.create_table(
        "tutor_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("learning_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_type", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("user_response", sa.Text(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_tutor_steps_session_id", "tutor_steps", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_tutor_steps_session_id", table_name="tutor_steps")
    op.drop_table("tutor_steps")
    op.drop_index("ix_learning_sessions_profile_id", table_name="learning_sessions")
    op.drop_table("learning_sessions")
