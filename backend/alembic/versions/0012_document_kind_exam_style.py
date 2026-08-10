"""자료 유형(kind) + 기출 스타일 프로파일 자리.

위저드가 파일별로 고르는 유형(교재/슬라이드/필기/기출)이 지금까지 프론트
상태에만 있고 서버로 오지 않았다. documents.kind에 받아서:
  - kind=exam 문서는 문제은행 생성에서 제외 (기출 복사 방지, QUIZ.md §0)
  - 대신 발문 스타일·개념 빈도를 뽑아 courses.exam_style_profile에 저장,
    본문 자료의 문제 생성에 반영 (§2-③)

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("kind", sa.String(20), nullable=False, server_default="textbook"),
    )
    op.add_column(
        "courses",
        sa.Column("exam_style_profile", postgresql.JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("courses", "exam_style_profile")
    op.drop_column("documents", "kind")
