"""materials/concepts/concept_prerequisites 테이블 생성 (Ingestion 도메인).

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import HALFVEC

from app.core.config import settings

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_EMBED_DIM = settings.SOLAR_EMBED_DIM


def upgrade() -> None:
    op.create_table(
        "materials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="parsing"),
        sa.Column("markdown", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "concepts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding", HALFVEC(_EMBED_DIM), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("material_id", "name", name="uq_concept_material_name"),
    )
    op.create_index("ix_concepts_material_id", "concepts", ["material_id"])

    op.create_table(
        "concept_prerequisites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("concept_id", sa.Integer(), nullable=False),
        sa.Column("prerequisite_concept_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["prerequisite_concept_id"], ["concepts.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "concept_id", "prerequisite_concept_id", name="uq_concept_prereq_edge"
        ),
    )
    op.create_index(
        "ix_concept_prerequisites_concept_id", "concept_prerequisites", ["concept_id"]
    )
    op.create_index(
        "ix_concept_prerequisites_prerequisite_concept_id",
        "concept_prerequisites",
        ["prerequisite_concept_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_concept_prerequisites_prerequisite_concept_id",
        table_name="concept_prerequisites",
    )
    op.drop_index(
        "ix_concept_prerequisites_concept_id", table_name="concept_prerequisites"
    )
    op.drop_table("concept_prerequisites")
    op.drop_index("ix_concepts_material_id", table_name="concepts")
    op.drop_table("concepts")
    op.drop_table("materials")
