"""[4.Repository] DB 조회/삽입 및 pgvector 유사도 검색 전담.

커리큘럼(JIT)은 materials의 개념 그래프와 diagnostic의 숙련도를 함께 읽는다.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.diagnostic.models import ConceptMastery, DiagnosticSession
from app.features.learning.models import Curriculum, LearningItem
from app.features.materials.models import Concept, ConceptPrerequisite


class LearningRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── 기존 데모(generate) ───────────────────────────────────
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

    # ── 개념 그래프 조회 ──────────────────────────────────────
    def get_concept(self, concept_id: int) -> Concept | None:
        return self.db.get(Concept, concept_id)

    def get_direct_prerequisites(self, concept_id: int) -> list[Concept]:
        """해당 개념이 직접 의존하는 선수 개념들 (선행 그래프 1-hop)."""
        stmt = (
            select(Concept)
            .join(
                ConceptPrerequisite,
                ConceptPrerequisite.prerequisite_concept_id == Concept.id,
            )
            .where(ConceptPrerequisite.concept_id == concept_id)
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

    # ── 커리큘럼 캐시 ─────────────────────────────────────────
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
