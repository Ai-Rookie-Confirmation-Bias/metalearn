"""문항 스타일 표시 — standard | exam.

기출 스타일은 별도 은행이 아니라 같은 quiz_items에 **표시만 달고** 들어간다.
기본 생성은 standard 그대로, [기출문제 스타일로 생성]을 누르면 exam 문항이
추가(append)된다. "기출만 풀기"는 세션 샘플링이 이 컬럼으로 거른다.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "quiz_items",
        sa.Column("style", sa.String(16), nullable=False, server_default="standard"),
    )


def downgrade() -> None:
    op.drop_column("quiz_items", "style")
