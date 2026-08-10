"""확정 화면(⑥) — 사용자가 뺀 선수 과목을 표시할 자리.

진단이 끝나면 지금까지는 **묻지 않고 목차에 끼웠다.** 그 사이에 화면을 하나
넣어 "이렇게 배우면 될까요"를 묻는다. 거기서 뺀 과목이 여기 남는다.

**지우지 않고 표시만 하는 이유가 있다.** 행을 지우면 다음 진단이 같은 과목을
또 제안하고(선수 판정은 자료에서 나오므로 사용자 답과 무관하게 되살아난다),
왜 빠졌는지도 못 되짚는다. `rejected_by`와 같은 사정이다.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "course_prereqs",
        sa.Column(
            "excluded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("course_prereqs", "excluded")
