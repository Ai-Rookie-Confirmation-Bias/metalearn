"""concepts에 출처 컬럼 추가: source(document|llm) + source_anchor(헤딩 경로).

교재에서 추출한 개념은 원문 어느 섹션에서 나왔는지(source_anchor)를,
LLM이 보충한 선수개념은 source='llm'으로 출처를 명시한다 (ISSUE-008).
source_anchor는 커리큘럼 시점 JIT 깊이 확장 때 해당 섹션 텍스트를
다시 찾는 키로도 쓰인다.

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "concepts",
        sa.Column("source", sa.String(length=16), nullable=False, server_default="document"),
    )
    op.add_column("concepts", sa.Column("source_anchor", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("concepts", "source_anchor")
    op.drop_column("concepts", "source")
