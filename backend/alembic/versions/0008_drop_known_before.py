"""seed_profiles.known_before 컬럼 제거

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("seed_profiles", "known_before")


def downgrade() -> None:
    op.add_column(
        "seed_profiles",
        sa.Column("known_before", postgresql.JSONB(), server_default="[]", nullable=False),
    )
