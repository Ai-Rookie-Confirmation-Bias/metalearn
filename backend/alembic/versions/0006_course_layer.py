"""코스 층 — 자료 묶기 · 역할 · 목차 복사본.

파싱(문서 층)과 학습(사용자 층) 사이가 비어 있어 "PPT + 교재"를 한 수업으로
묶을 자리가 없었다. 그리고 doc_topics는 문서 소유라 목차가 책당 한 벌뿐이라,
사용자가 목차를 고치면 같은 책을 보는 다른 사람에게까지 반영됐다.

course_topics가 그 복사본이다. 원본(doc_topics)은 건드리지 않는다.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # users 테이블이 아직 없어 FK를 걸지 않는다 (user_documents와 같은 사정).
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index("ix_courses_user_id", "courses", ["user_id"])

    op.create_table(
        "course_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "course_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "document_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("seq", sa.Integer(), server_default="0", nullable=False),
        sa.UniqueConstraint("course_id", "document_id", name="uq_course_document"),
    )
    op.create_index("ix_course_documents_course_id", "course_documents", ["course_id"])
    op.create_index(
        "ix_course_documents_document_id", "course_documents", ["document_id"]
    )

    op.create_table(
        "course_topics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "course_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        # 원본이 지워져도 고쳐놓은 단원은 남아야 한다 → SET NULL.
        sa.Column(
            "source_topic_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("doc_topics.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("origin", sa.String(16), server_default="book", nullable=False),
        sa.Column("plan", sa.String(16), server_default="normal", nullable=False),
        sa.Column(
            "anchor_concept_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.UniqueConstraint("course_id", "seq", name="uq_course_topic_seq"),
    )
    op.create_index("ix_course_topics_course_id", "course_topics", ["course_id"])
    op.create_index(
        "ix_course_topics_source_topic_id", "course_topics", ["source_topic_id"]
    )
    op.create_index(
        "ix_course_topics_anchor_concept_id", "course_topics", ["anchor_concept_id"]
    )


def downgrade() -> None:
    op.drop_table("course_topics")
    op.drop_table("course_documents")
    op.drop_table("courses")
