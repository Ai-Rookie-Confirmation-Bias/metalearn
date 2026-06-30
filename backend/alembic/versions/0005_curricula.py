"""curricula 테이블 생성 (JIT 적응형 커리큘럼).

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "curricula",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("concept_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("score", sa.Float(), nullable=False, server_default="0.3"),
        sa.Column("mode", sa.String(length=16), nullable=False, server_default="bridge"),
        sa.Column("prerequisite_ratio", sa.Float(), nullable=False, server_default="0"),
        sa.Column("main_ratio", sa.Float(), nullable=False, server_default="1"),
        sa.Column("blocks", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["diagnostic_sessions.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_curricula_concept_id", "curricula", ["concept_id"])


def downgrade() -> None:
    op.drop_index("ix_curricula_concept_id", table_name="curricula")
    op.drop_table("curricula")
