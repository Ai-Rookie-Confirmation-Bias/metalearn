"""[4.Repository] DB 조회/삽입 및 pgvector 유사도 검색 전담."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.learning.models import LearningItem


class LearningRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, content: str, embedding: list[float] | None = None) -> LearningItem:
        item = LearningItem(content=content, embedding=embedding)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def search_similar(self, embedding: list[float], limit: int = 5) -> list[LearningItem]:
        """pgvector 코사인 거리 기반 유사 항목 검색."""
        stmt = (
            select(LearningItem)
            .order_by(LearningItem.embedding.cosine_distance(embedding))
            .limit(limit)
        )
        return list(self.db.scalars(stmt))
