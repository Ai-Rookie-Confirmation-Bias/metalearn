"""다중 PDF 통합 — documents에 course_id/seq/role (1:N 코스↔문서).

한 코스가 여러 PDF를 순서대로 소유하도록 확장. course_id로 코스에 귀속,
seq로 학습 순서(primary 척추), role로 primary(트리 포함) vs supplementary
(RAG 근거로만) 구분. 기존 단일 문서 코스는 첫 문서가 seq=0/primary.

Revision ID: 0018
Revises: 0016
Create Date: 2026-07-08
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("course_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "documents",
        sa.Column("role", sa.String(16), nullable=False, server_default="primary"),
    )
    op.create_index("ix_documents_course_id", "documents", ["course_id"])
    op.create_foreign_key(
        "fk_documents_course_id", "documents", "courses",
        ["course_id"], ["id"], ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_documents_course_id", "documents", type_="foreignkey")
    op.drop_index("ix_documents_course_id", table_name="documents")
    op.drop_column("documents", "role")
    op.drop_column("documents", "seq")
    op.drop_column("documents", "course_id")
