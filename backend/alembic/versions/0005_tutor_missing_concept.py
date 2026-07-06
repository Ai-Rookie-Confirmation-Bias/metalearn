"""tutor_steps missing_concept_analysis

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tutor_steps",
        sa.Column(
            "missing_concept_analysis",
            postgresql.JSONB(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("tutor_steps", "missing_concept_analysis")
