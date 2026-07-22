"""교재 그림 AI 설명 — figure 주변 원문 근거로 생성한 설명(Layer 2+).

vision 모델 없이 그림 주변 원문(refined_elements 같은 페이지)을 근거로 "이 그림이
무엇을 보여주는지" LLM이 설명한다(환각 억제: 원문 근거). "설명 + 그림" 렌더용.

Revision ID: 0023
Revises: 0022
Create Date: 2026-07-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("doc_figures", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("doc_figures", "description")
