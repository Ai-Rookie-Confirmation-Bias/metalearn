"""학습자 모델 — learner_mastery, current_unit_order

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "seed_profiles",
        sa.Column(
            "learner_mastery",
            postgresql.JSONB(),
            server_default="{}",
            nullable=False,
        ),
    )
    op.add_column(
        "seed_profiles",
        sa.Column(
            "current_unit_order",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("seed_profiles", "current_unit_order")
    op.drop_column("seed_profiles", "learner_mastery")
