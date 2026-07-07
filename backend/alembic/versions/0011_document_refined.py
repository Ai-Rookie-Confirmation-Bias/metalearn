"""documents에 정제 결과 컬럼 추가: refined_elements(JSONB) + profile.

정제 v1 (ISSUE-014): 파서 elements를 정제(removed 마킹 + 파트 경계 +
프로파일 판정)해 운영용 원본으로 저장한다. raw_text는 보존용 원본으로
불변 — 정제 실수 시 재파싱 없이 refined_elements만 재생성한다.
profile은 문서 성격 라벨(linked|enumerative|mixed) — v1에서는 저장만.

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("refined_elements", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "documents", sa.Column("profile", sa.String(length=16), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("documents", "profile")
    op.drop_column("documents", "refined_elements")
