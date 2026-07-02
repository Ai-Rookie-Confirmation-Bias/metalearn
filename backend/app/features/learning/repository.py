"""[4.Repository] DB 조회/삽입 및 pgvector 유사도 검색 전담."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.diagnostic.models import ConceptMastery, DiagnosticSession
from app.features.documents.models import Concept, ConceptEdge
from app.features.learning.models import Curriculum, LearningItem


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
        stmt = (
            select(LearningItem)
            .order_by(LearningItem.embedding.cosine_distance(embedding))
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def get_concept(self, concept_id: int) -> Concept | None:
        return self.db.get(Concept, concept_id)

    def get_direct_prerequisites(self, concept_id: int) -> list[Concept]:
        stmt = (
            select(Concept)
            .join(ConceptEdge, ConceptEdge.to_concept_id == Concept.id)
            .where(
                ConceptEdge.from_concept_id == concept_id,
                ConceptEdge.kind == "prerequisite",
            )
            .order_by(Concept.id)
        )
        return list(self.db.scalars(stmt))

    def session_exists(self, session_id: int) -> bool:
        return self.db.get(DiagnosticSession, session_id) is not None

    def get_mastery(self, *, session_id: int, concept_id: int) -> ConceptMastery | None:
        stmt = select(ConceptMastery).where(
            ConceptMastery.session_id == session_id,
            ConceptMastery.concept_id == concept_id,
        )
        return self.db.scalars(stmt).first()

    def get_latest_curriculum(
        self, *, concept_id: int, session_id: int | None
    ) -> Curriculum | None:
        stmt = (
            select(Curriculum)
            .where(Curriculum.concept_id == concept_id)
            .order_by(Curriculum.id.desc())
        )
        if session_id is not None:
            stmt = stmt.where(Curriculum.session_id == session_id)
        return self.db.scalars(stmt).first()

    def save_curriculum(
        self,
        *,
        concept_id: int,
        session_id: int | None,
        score: float,
        mode: str,
        prerequisite_ratio: float,
        main_ratio: float,
        blocks: list[dict],
    ) -> Curriculum:
        curriculum = Curriculum(
            concept_id=concept_id,
            session_id=session_id,
            score=score,
            mode=mode,
            prerequisite_ratio=prerequisite_ratio,
            main_ratio=main_ratio,
            blocks=blocks,
        )
        self.db.add(curriculum)
        self.db.commit()
        self.db.refresh(curriculum)
        return curriculum
