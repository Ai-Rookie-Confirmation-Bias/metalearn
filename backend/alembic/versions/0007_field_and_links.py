"""12.5 분야 판정 · 16' 기각 검사 · 18 자료끼리 연결.

세 가지가 들어온다.

  ① documents.field / prereq_probe
     "이 자료는 무슨 분야고 그 앞엔 뭐가 필요한가". **문서 소유**라 지문
     재사용이 그대로 먹는다 — 같은 책은 누가 올리든 같은 판정을 받는다.
     파이프라인에서 LLM이 흔들리는 지점을 여기 하나로 가둔 것이다.

  ② course_prereqs
     ①을 코스의 실제 자료들과 대조해 "이미 가르치는 것"을 걸러낸 결과.
     판정이 코스 소유인 이유: PPT의 선수를 같이 올린 교재가 커버할 수 있다.

  ③ concept_links / document_pairs
     다른 문서의 같은 개념끼리 잇는다. PPT 표제어 ↔ 교재 설명.
     **문서쌍 소유**라 같은 두 책을 쓰는 다음 사람이 다시 계산하지 않는다.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── ① 분야 판정 (문서 소유) ──────────────────────────────────
    op.add_column("documents", sa.Column("field", sa.String(128), nullable=True))
    op.add_column(
        "documents",
        sa.Column("prereq_probe", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # ── ② 기각 검사 결과 (코스 소유) ─────────────────────────────
    op.create_table(
        "course_prereqs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "course_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("subject", sa.String(256), nullable=False),
        sa.Column("item", sa.String(512), nullable=False),
        sa.Column("why", sa.Text(), nullable=True),
        sa.Column("seq", sa.Integer(), server_default="0", nullable=False),
        sa.Column("ordered", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("status", sa.String(16), server_default="pass", nullable=False),
        # 되짚기용 — 문턱값(0.49)을 나중에 옮길 때 이게 근거가 된다.
        sa.Column("similarity", sa.Float(), nullable=True),
        sa.Column("rejected_by", sa.Text(), nullable=True),
        # 24번 진단이 채운다. known | heard | unknown
        sa.Column("known", sa.String(16), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint("course_id", "subject", "item", name="uq_course_prereq"),
    )
    op.create_index("ix_course_prereqs_course_id", "course_prereqs", ["course_id"])

    # ── ③ 개념 연결 (문서쌍 소유) ────────────────────────────────
    # 무방향이다. 항상 a < b로 정규화해 (x,y)와 (y,x)가 따로 쌓이지 않게 한다.
    op.create_table(
        "concept_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "concept_a_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "concept_b_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("similarity", sa.Float(), nullable=False),
        sa.Column("kind", sa.String(16), server_default="same", nullable=False),
        sa.Column("verified_by", sa.String(16), server_default="embed", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint("concept_a_id", "concept_b_id", name="uq_concept_link"),
    )
    op.create_index("ix_concept_links_a", "concept_links", ["concept_a_id"])
    op.create_index("ix_concept_links_b", "concept_links", ["concept_b_id"])

    # 링크 0개가 "아직 안 쟀다"인지 "재봤는데 안 겹친다"인지 구분한다.
    # 없으면 코스를 열 때마다 개념 수만큼 최근접 조회를 다시 돈다.
    op.create_table(
        "document_pairs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_a_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "document_b_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("link_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint("document_a_id", "document_b_id", name="uq_document_pair"),
    )
    op.create_index("ix_document_pairs_a", "document_pairs", ["document_a_id"])
    op.create_index("ix_document_pairs_b", "document_pairs", ["document_b_id"])


def downgrade() -> None:
    op.drop_table("document_pairs")
    op.drop_table("concept_links")
    op.drop_table("course_prereqs")
    op.drop_column("documents", "prereq_probe")
    op.drop_column("documents", "field")
