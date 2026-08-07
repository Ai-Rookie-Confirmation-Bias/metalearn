"""24 진단 — 목표·성향·선수 확인 결과를 담을 자리.

진단은 시험이 아니라 **설정**이다. 실측에서 문항 자동 생성이 못 쓸 수준이었고
(책 밖 1/6 · 책 안 1/4), 대신 오답만 생성하는 방식이 14/15로 됐다. 그래서
묻는 방식은 체크리스트이고 문항은 "정말 아는지" 확인에만 쓴다.

  courses.goal / deadline_weeks   왜·언제까지 → 분량(plan) 결정
  courses.style                   설명 형식 취향 → 설명 생성 프롬프트
  courses.diagnosed_at            진단을 했나
  course_prereqs.verified         자기 말(known)을 문항으로 재본 결과

⚠️ `style`은 **학습 효과 근거가 없다.** 러닝 스타일 맞춤은 반증됐다
(Pashler 2008). 이탈 방지용이다 — 읽기 싫은 형식이면 안 읽는다.

`known`은 0007에서 이미 만들어 뒀다. 여기서는 `verified`만 더한다.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("courses", sa.Column("goal", sa.String(16), nullable=True))
    op.add_column("courses", sa.Column("deadline_weeks", sa.Integer(), nullable=True))
    op.add_column("courses", sa.Column("style", sa.String(16), nullable=True))
    op.add_column(
        "courses",
        sa.Column("diagnosed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # NULL = 안 물어봤다. 문항을 다 낼 수는 없으므로 대부분 NULL로 남는다.
    op.add_column(
        "course_prereqs", sa.Column("verified", sa.Boolean(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("course_prereqs", "verified")
    op.drop_column("courses", "diagnosed_at")
    op.drop_column("courses", "style")
    op.drop_column("courses", "deadline_weeks")
    op.drop_column("courses", "goal")
