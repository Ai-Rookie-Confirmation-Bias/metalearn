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

    def append_document_items(self, items: list[QuizItem]) -> None:
        """리필 생성 — 기존 은행을 유지한 채 새 문항을 추가한다.

        중복 제거는 서비스가 한다 (문항 내용 비교는 데이터 로직이라 여기선 저장만).
        """
        self.db.add_all(items)
        self.db.commit()

    def list_document_items(
        self, course_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[QuizItem]:
        """이 문서의 기존 은행 전체 — 리필 시 중복 대조용."""
        return list(
            self.db.execute(
                select(QuizItem).where(
                    QuizItem.course_id == course_id,
                    QuizItem.document_id == document_id,
                )
            )
            .scalars()
            .all()
        )

    def sample_items(
        self,
        course_id: uuid.UUID,
        document_id: uuid.UUID,
        toc_indexes: list[int],
        count: int,
        exclude_ids: list[uuid.UUID] | None = None,
    ) -> tuple[list[QuizItem], int]:
        """범위 내 무작위 샘플 — **안 푼 문항 우선.**

        exclude_ids(클라이언트가 푼 문항, 오래된 순)를 뺀 풀에서 먼저 뽑고,
        모자라면 exclude_ids 순서대로(= 푼 지 오래된 것부터) 복습으로 채운다.
        반환: (문항 목록, 그중 복습 재등장 수). 어떤 경우에도 풀이 있으면
        빈손으로 돌려보내지 않는다.
        """
        exclude = exclude_ids or []
        base = (
            QuizItem.course_id == course_id,
            QuizItem.document_id == document_id,
            QuizItem.toc_index.in_(toc_indexes),
            QuizItem.verified.is_(True),
        )
        stmt = select(QuizItem).where(*base)
        if exclude:
            stmt = stmt.where(QuizItem.id.not_in(exclude))
        fresh = list(
            self.db.execute(stmt.order_by(func.random()).limit(count)).scalars().all()
        )
        shortfall = count - len(fresh)
        if shortfall <= 0 or not exclude:
            return fresh, 0

        # 복습 채움 — 클라이언트가 준 순서(오래된 순)를 보존한다
        solved_rows = {
            row.id: row
            for row in self.db.execute(
                select(QuizItem).where(*base, QuizItem.id.in_(exclude))
            ).scalars()
        }
        recycled = [
            solved_rows[i] for i in exclude if i in solved_rows
        ][:shortfall]
        return fresh + recycled, len(recycled)

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
