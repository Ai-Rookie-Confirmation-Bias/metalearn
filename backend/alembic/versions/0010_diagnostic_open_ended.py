"""진단 문항 서술형 지원

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "diagnostic_questions",
        sa.Column(
            "question_type",
            sa.String(length=32),
            server_default="multiple_choice",
            nullable=False,
        ),
    )
    op.add_column(
        "diagnostic_questions",
        sa.Column("reference_answer", sa.Text(), nullable=True),
    )
    op.alter_column(
        "diagnostic_questions",
        "correct_index",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.add_column(
        "diagnostic_answers",
        sa.Column("user_response", sa.Text(), nullable=True),
    )
    op.alter_column(
        "diagnostic_answers",
        "user_choice_index",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "diagnostic_answers",
        "user_choice_index",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_column("diagnostic_answers", "user_response")
    op.alter_column(
        "diagnostic_questions",
        "correct_index",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_column("diagnostic_questions", "reference_answer")
    op.drop_column("diagnostic_questions", "question_type")
