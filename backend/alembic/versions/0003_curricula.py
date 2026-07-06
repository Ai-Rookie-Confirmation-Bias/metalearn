"""curricula table

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "curricula",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("seed_profiles.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("units", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("chapter_groups", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("weakness_count", sa.Integer(), server_default="0"),
        sa.Column("total_units", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("curricula")
