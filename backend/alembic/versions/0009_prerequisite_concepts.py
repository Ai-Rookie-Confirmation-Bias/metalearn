"""seed_profiles.prerequisite_concepts 추가

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "seed_profiles",
        sa.Column(
            "prerequisite_concepts",
            postgresql.JSONB(),
            server_default="[]",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("seed_profiles", "prerequisite_concepts")
