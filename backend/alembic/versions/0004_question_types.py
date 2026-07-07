"""diagnostic_questions에 문항 유형(mcq/cloze/inverse) 컬럼 확장.

- qtype/expected_answer/acceptable_answers/answer_text 추가
- options/answer_index는 인출형에서 비므로 NULL 허용

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "diagnostic_questions",
        sa.Column("qtype", sa.String(length=16), nullable=False, server_default="mcq"),
    )
    op.add_column(
        "diagnostic_questions", sa.Column("expected_answer", sa.Text(), nullable=True)
    )
    op.add_column(
        "diagnostic_questions",
        sa.Column("acceptable_answers", sa.JSON(), nullable=True),
    )
    op.add_column(
        "diagnostic_questions", sa.Column("answer_text", sa.Text(), nullable=True)
    )
    op.alter_column("diagnostic_questions", "options", existing_type=sa.JSON(), nullable=True)
    op.alter_column(
        "diagnostic_questions", "answer_index", existing_type=sa.Integer(), nullable=True
    )


def downgrade() -> None:
    op.alter_column(
        "diagnostic_questions", "answer_index", existing_type=sa.Integer(), nullable=False
    )
    op.alter_column("diagnostic_questions", "options", existing_type=sa.JSON(), nullable=False)
    op.drop_column("diagnostic_questions", "answer_text")
    op.drop_column("diagnostic_questions", "acceptable_answers")
    op.drop_column("diagnostic_questions", "expected_answer")
    op.drop_column("diagnostic_questions", "qtype")
