"""배치고사 세션 — diagnostic_sessions.kind/state (ISSUE-015, 병합 v2).

기존 진단(kind='full')과 배치고사(kind='placement')를 한 테이블에서 구분.
state JSONB는 depth 하강 진행 상태(모드·계획·현재 위치·응답 이력)를 담는다.

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "diagnostic_sessions",
        sa.Column("kind", sa.String(16), nullable=False, server_default="full"),
    )
    op.add_column(
        "diagnostic_sessions",
        sa.Column("state", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("diagnostic_sessions", "state")
    op.drop_column("diagnostic_sessions", "kind")
