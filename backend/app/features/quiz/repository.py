"""[4.Repository] quiz_items / quiz_attempts DB 접근."""
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.features.quiz.models import QuizAttempt, QuizItem


class QuizRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def replace_document_items(
        self, course_id: uuid.UUID, document_id: uuid.UUID, items: list[QuizItem]
    ) -> None:
        """재생성 = 기존 문항 전체 교체 (반쯤 섞인 은행 금지, docs/QUIZ.md §2-⑦)."""
        self.db.execute(
            delete(QuizItem).where(
                QuizItem.course_id == course_id, QuizItem.document_id == document_id
            )
        )
        self.db.add_all(items)
        self.db.commit()

    def toc_summary(self, course_id: uuid.UUID) -> list[tuple]:
        """(document_id, toc_index, toc_title, count) — verified만."""
        rows = self.db.execute(
            select(
                QuizItem.document_id,
                QuizItem.toc_index,
                func.max(QuizItem.toc_title),
                func.count(),
            )
            .where(QuizItem.course_id == course_id, QuizItem.verified.is_(True))
            .group_by(QuizItem.document_id, QuizItem.toc_index)
            .order_by(QuizItem.document_id, QuizItem.toc_index)
        ).all()
        return rows

    def sample_items(
        self,
        course_id: uuid.UUID,
        document_id: uuid.UUID,
        toc_indexes: list[int],
        count: int,
    ) -> list[QuizItem]:
        return list(
            self.db.execute(
                select(QuizItem)
                .where(
                    QuizItem.course_id == course_id,
                    QuizItem.document_id == document_id,
                    QuizItem.toc_index.in_(toc_indexes),
                    QuizItem.verified.is_(True),
                )
                .order_by(func.random())
                .limit(count)
            )
            .scalars()
            .all()
        )

    def get_item(self, item_id: uuid.UUID) -> QuizItem | None:
        return self.db.get(QuizItem, item_id)

    def record_attempt(
        self,
        item_id: uuid.UUID,
        correct: bool,
        user_input,
        user_id: uuid.UUID | None = None,
    ) -> None:
        self.db.add(
            QuizAttempt(
                user_id=user_id,
                quiz_item_id=item_id,
                correct=correct,
                user_input={"value": user_input},
            )
        )
        self.db.commit()
