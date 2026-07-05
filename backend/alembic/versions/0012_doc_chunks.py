"""RAG 문서 청크 테이블 + 개념→청크 출처 FK (팀 스키마 doc_chunks 정렬).

지금까지 청크는 추출 때 메모리에서 만들고 버렸다. 영속화하면:
- RAG 검색 계층 확보 (컨텍스트 주입·문제 근거의 검색 단위)
- 개념의 출처가 문자열 anchor → chunk FK로 승격 (ISSUE-011 앵커 부정확
  구조 해결, JIT 원문 조회가 조인 한 번)
- element_from/to로 refined_elements의 정밀 좌표까지 드릴다운 가능

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import HALFVEC

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "doc_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", HALFVEC(4096), nullable=True),
        sa.Column("element_from", sa.Integer(), nullable=True),
        sa.Column("element_to", sa.Integer(), nullable=True),
        sa.Column("heading", sa.Text(), nullable=True),
        sa.Column("part_index", sa.Integer(), nullable=True),
        sa.Column("page_from", sa.Integer(), nullable=True),
        sa.Column("page_to", sa.Integer(), nullable=True),
    )
    op.add_column(
        "concepts",
        sa.Column(
            "source_chunk_id",
            sa.Integer(),
            sa.ForeignKey("doc_chunks.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("concepts", "source_chunk_id")
    op.drop_table("doc_chunks")
