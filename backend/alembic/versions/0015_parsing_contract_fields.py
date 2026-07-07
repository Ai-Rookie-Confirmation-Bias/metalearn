"""parsing 파이프라인 병합 — 계약 필드 유니온 + 진단 테이블 (병합 2단계, UUID 포팅)

정본(UUID) 스키마 위에 parsing 상류(문서 섭취→정제→개념추출→진단)가 쓰는
컬럼/테이블을 얹는다. parsing 계보 마이그레이션(0002_materials 등)은 이중
head 방지를 위해 삭제됨 — 전체 스쿼시는 ISSUE-001 팀 합의 후 별도 진행.

- documents: refined_elements/profile/error 추가, storage_url nullable 완화
- doc_chunks: 청킹 메타(element_from/to, heading, part_index) 추가
- concepts: embedding(halfvec)/source_anchor/source_chunk_id/created_at 추가,
  key nullable 완화(섭취 시점엔 key 없음 — 씨앗 조립에서 채움. TODO: 합의 후 복원)
- concept_mastery: 진단 세션 작업 상태(session_id/answered_count/resolved/locked)
- diagnostic_sessions / diagnostic_questions 신설

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import HALFVEC
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBED_DIM = 4096


def _uuid_pk() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def upgrade() -> None:
    # 1) documents — 정제 v1(ISSUE-014) 산출물 + 실패 사유
    op.add_column("documents", sa.Column("refined_elements", postgresql.JSONB(), nullable=True))
    op.add_column("documents", sa.Column("profile", sa.String(16), nullable=True))
    op.add_column("documents", sa.Column("error", sa.Text(), nullable=True))
    # 섭취 파이프라인은 스토리지 없이 원문만 저장 → nullable 완화
    op.alter_column("documents", "storage_url", existing_type=sa.String(1024), nullable=True)

    # 2) doc_chunks — 청킹 메타(요소 좌표·헤딩 경로·파트 번호)
    op.add_column("doc_chunks", sa.Column("element_from", sa.Integer(), nullable=True))
    op.add_column("doc_chunks", sa.Column("element_to", sa.Integer(), nullable=True))
    op.add_column("doc_chunks", sa.Column("heading", sa.Text(), nullable=True))
    op.add_column("doc_chunks", sa.Column("part_index", sa.Integer(), nullable=True))

    # 3) concepts — 상류가 저장한 개념 임베딩(query 모델, ISSUE-015)과 원문 출처
    op.add_column("concepts", sa.Column("embedding", HALFVEC(EMBED_DIM), nullable=True))
    op.add_column("concepts", sa.Column("source_anchor", sa.Text(), nullable=True))
    op.add_column(
        "concepts",
        sa.Column(
            "source_chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("doc_chunks.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "concepts",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # TODO(ISSUE-001 팀 합의 후): 섭취가 key를 생산하게 되면 NOT NULL 복원
    op.alter_column("concepts", "key", existing_type=sa.String(128), nullable=True)

    # 4) diagnostic_sessions — 코스당 진단 실행 세션
    op.create_table(
        "diagnostic_sessions",
        _uuid_pk(),
        sa.Column(
            "course_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_diagnostic_sessions_course_id", "diagnostic_sessions", ["course_id"])

    # 5) diagnostic_questions — 세션 문항 풀(정오답 기록 포함)
    op.create_table(
        "diagnostic_questions",
        _uuid_pk(),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("diagnostic_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "concept_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("concepts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("qtype", sa.String(16), nullable=False, server_default="mcq"),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=True),
        sa.Column("answer_index", sa.Integer(), nullable=True),
        sa.Column("expected_answer", sa.Text(), nullable=True),
        sa.Column("acceptable_answers", postgresql.JSONB(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("answered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("selected_index", sa.Integer(), nullable=True),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_diagnostic_questions_session_id", "diagnostic_questions", ["session_id"])
    op.create_index("ix_diagnostic_questions_concept_id", "diagnostic_questions", ["concept_id"])

    # 6) concept_mastery — 진단 세션 작업 상태 (PK는 그대로 user_id×concept_id,
    #    세션 재시작 시 같은 행을 업서트로 재사용)
    op.add_column(
        "concept_mastery",
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("diagnostic_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_concept_mastery_session_id", "concept_mastery", ["session_id"])
    op.add_column(
        "concept_mastery",
        sa.Column("answered_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "concept_mastery",
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "concept_mastery",
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("concept_mastery", "locked")
    op.drop_column("concept_mastery", "resolved")
    op.drop_column("concept_mastery", "answered_count")
    op.drop_index("ix_concept_mastery_session_id", table_name="concept_mastery")
    op.drop_column("concept_mastery", "session_id")
    op.drop_table("diagnostic_questions")
    op.drop_table("diagnostic_sessions")
    op.alter_column("concepts", "key", existing_type=sa.String(128), nullable=False)
    op.drop_column("concepts", "created_at")
    op.drop_column("concepts", "source_chunk_id")
    op.drop_column("concepts", "source_anchor")
    op.drop_column("concepts", "embedding")
    op.drop_column("doc_chunks", "part_index")
    op.drop_column("doc_chunks", "heading")
    op.drop_column("doc_chunks", "element_to")
    op.drop_column("doc_chunks", "element_from")
    op.alter_column("documents", "storage_url", existing_type=sa.String(1024), nullable=False)
    op.drop_column("documents", "error")
    op.drop_column("documents", "profile")
    op.drop_column("documents", "refined_elements")
