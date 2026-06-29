"""document_chunks concept_id

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column("concept_id", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_document_chunks_concept_id",
        "document_chunks",
        ["document_id", "concept_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_concept_id", table_name="document_chunks")
    op.drop_column("document_chunks", "concept_id")
