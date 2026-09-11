"""개념의 근거 문장 — concepts.evidence_sentences 추가.

[[조각 seq, 문장 seq], …] 형태로 5-b(segment_sentences)를 가리킨다.
조각 번호를 함께 두는 이유는 개념 ↔ 조각이 다대다라 문장 번호만으로는
어느 조각의 문장인지 특정되지 않기 때문이다.

NULL은 "이 기능 이전에 추출된 문서", 빈 배열은 "LLM이 근거를 못 찾음"으로
구분한다 — 커버리지 통계가 둘을 섞으면 거짓말이 된다.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "concepts",
        sa.Column("evidence_sentences", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("concepts", "evidence_sentences")
