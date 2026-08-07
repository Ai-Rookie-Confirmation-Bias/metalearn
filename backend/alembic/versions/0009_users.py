"""users — 소셜 로그인(Google/Naver) 계정 + 그동안 못 걸던 FK 둘.

`feat/oauth-login`의 마이그레이션을 그대로 못 가져온다. 그쪽은 users가 이미
있는 상태에서 컬럼을 **추가**하는 0020이고(0002에서 만든 테이블), 이 브랜치는
users가 아예 없다. 그래서 **최종 모양으로 한 번에** 만든다 — 저쪽의
0002(생성) + 0020(provider/provider_sub/name, password_hash nullable)을 합친 것.

같이 닫는 빚: `courses.user_id`와 `user_documents.user_id`에 FK가 없었다.
"users 테이블이 아직 없어 FK를 걸지 않는다"가 0006 주석과 parsing/models.py에
그대로 남아 있다(docs/STATUS.md §5). 두 테이블 모두 지금 0행이라 지금이 제일
싸게 거는 시점이다.

기존 파싱 문서는 dev 유저 소유로 붙인다. 안 붙이면 책장이 소유로 걸러지는
순간(2단계) 이미 파싱해 둔 자료가 통째로 안 보인다.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# core/deps.py의 DEV_USER_ID와 같은 값. 로그인 전 경로가 전부 이 유저를 본다.
DEV_USER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        # 소셜 사용자는 비밀번호가 없다.
        sa.Column("password_hash", sa.String(255), nullable=True),
        # local | google | naver
        sa.Column(
            "provider", sa.String(20), nullable=False, server_default="local"
        ),
        # 제공자측 고유 id(구글 sub, 네이버 id). local 사용자는 NULL.
        sa.Column("provider_sub", sa.String(255), nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        # Postgres는 NULL을 서로 다르게 취급하므로 local 사용자끼리는 안 부딪힌다.
        sa.UniqueConstraint("provider", "provider_sub", name="uq_users_provider_sub"),
    )

    op.execute(
        sa.text(
            "INSERT INTO users (id, email, provider) "
            f"VALUES ('{DEV_USER_ID}', 'dev@local', 'local') "
            "ON CONFLICT (id) DO NOTHING"
        )
    )

    # 이미 파싱해 둔 문서를 dev 유저 책장에 넣는다.
    op.execute(
        sa.text(
            "INSERT INTO user_documents (id, user_id, document_id, role) "
            f"SELECT gen_random_uuid(), '{DEV_USER_ID}', d.id, 'skeleton' "
            "FROM documents d "
            "ON CONFLICT ON CONSTRAINT uq_user_document DO NOTHING"
        )
    )

    op.create_foreign_key(
        "fk_user_documents_user", "user_documents", "users",
        ["user_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_courses_user", "courses", "users",
        ["user_id"], ["id"], ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_courses_user", "courses", type_="foreignkey")
    op.drop_constraint("fk_user_documents_user", "user_documents", type_="foreignkey")
    op.drop_table("users")
