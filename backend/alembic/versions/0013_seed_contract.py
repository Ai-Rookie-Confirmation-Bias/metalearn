"""씨앗 산출물 계약(docs/ii.md) 구조: chapters/sections + concepts.key + enrollment 확장.

ISSUE-017: 커리큘럼 파트 인수인계 계약이 요구하는 뼈대 —
- chapters/sections: 씨앗이 생성하는 커리큘럼 트리 (gen_status는 pending 고정)
- concepts.key: 코스 내 유니크 영문 슬러그 (생성 프롬프트 키)
- enrollments: 진단 완료 시 floor/ceiling/purpose 확정

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chapters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "course_id",
            sa.Integer(),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("origin", sa.String(16), nullable=False, server_default="book"),
        sa.Column("gen_status", sa.String(16), nullable=False, server_default="pending"),
    )
    op.create_table(
        "sections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "chapter_id",
            sa.Integer(),
            sa.ForeignKey("chapters.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "concept_id",
            sa.Integer(),
            sa.ForeignKey("concepts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
    )
    op.add_column("concepts", sa.Column("key", sa.String(128), nullable=True))
    op.add_column("enrollments", sa.Column("floor_concept_id", sa.Integer(), nullable=True))
    op.add_column("enrollments", sa.Column("ceiling_concept_id", sa.Integer(), nullable=True))
    op.add_column(
        "enrollments",
        sa.Column("floor_found", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("enrollments", sa.Column("purpose", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("enrollments", "purpose")
    op.drop_column("enrollments", "floor_found")
    op.drop_column("enrollments", "ceiling_concept_id")
    op.drop_column("enrollments", "floor_concept_id")
    op.drop_column("concepts", "key")
    op.drop_table("sections")
    op.drop_table("chapters")
