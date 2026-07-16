"""교재 그림 저장 — Layer 2(원문 이미지 재사용).

Document Parse가 base64_encoding 파라미터로 돌려주는 figure/chart 크롭 이미지를
문서 단위로 보관한다. AI가 그리는 게 아니라 원문에서 추출 — 환각 0, "근거 없이
지어내지 않는다" 원칙과 정합(그림 자체가 근거). 절 생성 시 근거 청크의 페이지와
매칭해 image 블록으로 서빙된다.

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "doc_figures",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("element_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(32), nullable=False, server_default="figure"),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("mime", sa.String(64), nullable=False, server_default="image/png"),
        sa.Column("data", sa.LargeBinary(), nullable=False),
    )
    op.create_index("ix_doc_figures_document_page", "doc_figures", ["document_id", "page"])


def downgrade() -> None:
    op.drop_index("ix_doc_figures_document_page", table_name="doc_figures")
    op.drop_table("doc_figures")
