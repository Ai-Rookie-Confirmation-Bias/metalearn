"""밀도 지표 교체 — documents.chars_per_page 추가.

조각당 평균 글자수는 조각 예산(4,000자)의 함수라 자료 밀도를 재지 못했다.
실측 3권에서 조각당 평균이 3,212 / 3,351 / 3,557로 붙어 나와 슬라이드 자료까지
'본문 가능'으로 판정됐다. 페이지당 글자수는 299 / 1,266 / 3,396으로 갈린다.

기존 avg_segment_chars는 참고용으로 남긴다 — 조각화가 어떻게 됐는지는
여전히 알아야 하고, 지우면 이전 문서의 값도 함께 사라진다.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents", sa.Column("chars_per_page", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("documents", "chars_per_page")
