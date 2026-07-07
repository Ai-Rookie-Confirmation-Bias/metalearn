"""팀 스키마 정렬: users/courses/enrollments 부모 추가 + 테이블/컬럼 rename.

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-30
"""
from typing import Sequence, Union

import bcrypt
import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEV_PASSWORD_HASH = bcrypt.hashpw(b"dev", bcrypt.gensalt(rounds=12)).decode()


def upgrade() -> None:
    # ── 1. users ──────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("email"),
    )
    op.execute(
        sa.text(
            "INSERT INTO users (email, password_hash) VALUES ('dev@local', :hash)"
        ).bindparams(hash=_DEV_PASSWORD_HASH)
    )

    # ── 2. materials → documents ─────────────────────────────
    op.rename_table("materials", "documents")
    op.alter_column("documents", "markdown", new_column_name="raw_text")

    op.add_column("documents", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("storage_url", sa.Text(), nullable=True))
    op.execute(sa.text("UPDATE documents SET user_id = (SELECT id FROM users WHERE email = 'dev@local' LIMIT 1)"))
    op.alter_column("documents", "user_id", nullable=False)
    op.create_foreign_key(
        "documents_user_id_fkey", "documents", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_documents_user_id", "documents", ["user_id"])

    # status 값 정규화 (document_status)
    op.execute(
        sa.text(
            "UPDATE documents SET status = 'processing' "
            "WHERE status IN ('parsing', 'extracting')"
        )
    )

    # ── 3. courses (documents.title → courses.title) ─────────
    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("category", sa.String(length=256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_courses_document_id", "courses", ["document_id"])
    op.create_index("ix_courses_user_id", "courses", ["user_id"])

    op.execute(
        sa.text(
            "INSERT INTO courses (document_id, user_id, title, created_at) "
            "SELECT id, user_id, title, created_at FROM documents"
        )
    )
    op.drop_column("documents", "title")

    # ── 4. concepts: material_id → course_id, depth → depth_level
    op.add_column("concepts", sa.Column("course_id", sa.Integer(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE concepts c SET course_id = ("
            "  SELECT co.id FROM courses co WHERE co.document_id = c.material_id"
            ")"
        )
    )
    op.drop_constraint("concepts_material_id_fkey", "concepts", type_="foreignkey")
    op.drop_index("ix_concepts_material_id", table_name="concepts")
    op.drop_constraint("uq_concept_material_name", "concepts", type_="unique")
    op.drop_column("concepts", "material_id")
    op.alter_column("concepts", "course_id", nullable=False)
    op.create_foreign_key(
        "concepts_course_id_fkey", "concepts", "courses", ["course_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_concepts_course_id", "concepts", ["course_id"])
    op.create_unique_constraint("uq_concept_course_name", "concepts", ["course_id", "name"])
    op.alter_column("concepts", "depth", new_column_name="depth_level")

    # ── 5. concept_prerequisites → concept_edges ───────────
    op.rename_table("concept_prerequisites", "concept_edges")
    op.alter_column("concept_edges", "concept_id", new_column_name="from_concept_id")
    op.alter_column(
        "concept_edges", "prerequisite_concept_id", new_column_name="to_concept_id"
    )
    op.add_column(
        "concept_edges",
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="prerequisite"),
    )
    op.drop_index("ix_concept_prerequisites_concept_id", table_name="concept_edges")
    op.drop_index(
        "ix_concept_prerequisites_prerequisite_concept_id", table_name="concept_edges"
    )
    op.create_index("ix_concept_edges_from_concept_id", "concept_edges", ["from_concept_id"])
    op.create_index("ix_concept_edges_to_concept_id", "concept_edges", ["to_concept_id"])
    op.drop_constraint("uq_concept_prereq_edge", "concept_edges", type_="unique")
    op.create_unique_constraint(
        "uq_concept_edge", "concept_edges", ["from_concept_id", "to_concept_id", "kind"]
    )

    # ── 6. concept_masteries → concept_mastery ───────────────
    op.rename_table("concept_masteries", "concept_mastery")
    op.alter_column("concept_mastery", "p_known", new_column_name="strength")
    op.drop_index("ix_concept_masteries_session_id", table_name="concept_mastery")
    op.drop_index("ix_concept_masteries_concept_id", table_name="concept_mastery")
    op.create_index("ix_concept_mastery_session_id", "concept_mastery", ["session_id"])
    op.create_index("ix_concept_mastery_concept_id", "concept_mastery", ["concept_id"])

    # ── 7. diagnostic_sessions: material_id → course_id ──────
    op.add_column("diagnostic_sessions", sa.Column("course_id", sa.Integer(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE diagnostic_sessions ds SET course_id = ("
            "  SELECT co.id FROM courses co WHERE co.document_id = ds.material_id"
            ")"
        )
    )
    op.drop_constraint(
        "diagnostic_sessions_material_id_fkey", "diagnostic_sessions", type_="foreignkey"
    )
    op.drop_index("ix_diagnostic_sessions_material_id", table_name="diagnostic_sessions")
    op.drop_column("diagnostic_sessions", "material_id")
    op.alter_column("diagnostic_sessions", "course_id", nullable=False)
    op.create_foreign_key(
        "diagnostic_sessions_course_id_fkey",
        "diagnostic_sessions",
        "courses",
        ["course_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_diagnostic_sessions_course_id", "diagnostic_sessions", ["course_id"])

    # ── 8. enrollments ───────────────────────────────────────
    op.create_table(
        "enrollments",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column(
            "diag_status", sa.String(length=32), nullable=False, server_default="not_started"
        ),
        sa.Column("diag_q_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "course_id"),
    )

    op.execute(
        sa.text(
            "INSERT INTO enrollments (user_id, course_id, diag_status, created_at) "
            "SELECT c.user_id, c.id, "
            "CASE WHEN EXISTS ("
            "  SELECT 1 FROM diagnostic_sessions ds "
            "  WHERE ds.course_id = c.id AND ds.status = 'completed'"
            ") THEN 'completed' "
            "WHEN EXISTS ("
            "  SELECT 1 FROM diagnostic_sessions ds WHERE ds.course_id = c.id"
            ") THEN 'in_progress' "
            "ELSE 'not_started' END, "
            "c.created_at FROM courses c"
        )
    )


def downgrade() -> None:
    raise NotImplementedError("0009 downgrade is not supported")
