"""그림 인라인 복원 — doc_figures.char_offset 추가 (2-b단계).

조각 content 안에서 그림이 원래 있던 위치(문자 offset). 프론트가 본문을
여기서 끊고 이미지를 끼우면 원문 흐름이 복원된다. 없으면 그림이 전부
조각 맨 아래로 몰린다.

계산은 순수 로직이라 호출 0회다 — 요소 길이를 순서대로 누적하면 나온다.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "doc_figures",
        sa.Column("char_offset", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("doc_figures", "char_offset")
