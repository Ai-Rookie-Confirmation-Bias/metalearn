"""pgvector 확장 활성화 (첫 마이그레이션).

이후 모델 테이블은 `uv run alembic revision --autogenerate -m "..."`로 추가.

Revision ID: 0001
Revises:
Create Date: 2026-06-17
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
