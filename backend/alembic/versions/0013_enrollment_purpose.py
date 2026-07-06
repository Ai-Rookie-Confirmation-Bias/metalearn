"""enrollments.purpose 추가 — 정본(dev/docs/SCHEMA.md) 정합.

학습 목표(intent): exam | career | culture | hobby. 진단/코스 생성 시 확정.
placement 시딩과 무관하지만, 정본 스키마 정합을 맞춰 픽스처/진단 흐름이 purpose를
채울 수 있게 한다.

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("enrollments", sa.Column("purpose", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("enrollments", "purpose")
