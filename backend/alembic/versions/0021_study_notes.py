"""나의 요약 노트 — 절 단위 자기설명 메모 영속화.

튜터 패널의 "나의 요약 노트" 탭이 껍데기(로컬 state)였던 것을 실저장으로.
자기설명(인출 원리 ②)의 흔적이라 절 단위로 남긴다. (user, section) 1:1 upsert.
section FK는 CASCADE — 코스/챕터 삭제 시 함께 정리된다.

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "study_notes",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "section_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sections.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("study_notes")
