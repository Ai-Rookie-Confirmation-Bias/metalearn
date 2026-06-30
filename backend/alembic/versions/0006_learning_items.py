"""learning_items 테이블 생성 (기존 learning 데모용 — 누락분 보강).

LearningItem 모델은 초기부터 있었으나 이를 만드는 마이그레이션이 없어
/api/learning/generate 호출 시 테이블 부재로 실패했다.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import HALFVEC

from app.core.config import settings

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "learning_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("embedding", HALFVEC(settings.SOLAR_EMBED_DIM), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("learning_items")
