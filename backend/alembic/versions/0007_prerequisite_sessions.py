"""learning_sessions prerequisite 필드 추가

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "learning_sessions",
        sa.Column("session_type", sa.String(32), server_default="pdf_concept", nullable=False),
    )
    op.add_column(
        "learning_sessions",
        sa.Column(
            "parent_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("learning_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "learning_sessions",
        sa.Column("depth", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "learning_sessions",
        sa.Column("prereq_concept_title", sa.String(256), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("learning_sessions", "prereq_concept_title")
    op.drop_column("learning_sessions", "depth")
    op.drop_column("learning_sessions", "parent_session_id")
    op.drop_column("learning_sessions", "session_type")
