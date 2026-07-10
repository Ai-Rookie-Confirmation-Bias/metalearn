"""OAuth 소셜 로그인 — users에 provider/provider_sub/name + password_hash nullable.

소셜 로그인(Google/Naver) 도입. 소셜 사용자는 비밀번호가 없으므로 password_hash를
nullable로 완화하고, 인증 출처(provider)와 제공자측 고유 id(provider_sub)를 저장한다.
(provider, provider_sub) 유니크로 같은 소셜 계정의 중복 가입을 막는다 —
Postgres는 NULL을 서로 다르게 취급하므로 local 사용자(provider_sub=NULL)들끼리는
충돌하지 않는다.

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-08 (0017로 작성 → 병합 시 0019 뒤로 재연결, 2026-07-10)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "provider", sa.String(20), nullable=False, server_default="local"
        ),
    )
    op.add_column("users", sa.Column("provider_sub", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("name", sa.String(255), nullable=True))
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=True)
    op.create_unique_constraint(
        "uq_users_provider_sub", "users", ["provider", "provider_sub"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_users_provider_sub", "users", type_="unique")
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=False)
    op.drop_column("users", "name")
    op.drop_column("users", "provider_sub")
    op.drop_column("users", "provider")
