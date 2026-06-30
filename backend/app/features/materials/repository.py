"""[4.Repository] Material/Concept/Prerequisite DB 입출력 전담.

서비스 계층이 트랜잭션 경계를 잡도록, 여기서는 flush만 하고 commit은 하지 않는다.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.features.materials.models import Concept, ConceptPrerequisite, Material


class MaterialRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Material ──────────────────────────────────────────────
    def create_material(self, *, title: str, filename: str) -> Material:
        material = Material(title=title, filename=filename, status="parsing")
        self.db.add(material)
        self.db.flush()
        return material

    def get_material(self, material_id: int) -> Material | None:
        stmt = (
            select(Material)
            .where(Material.id == material_id)
            .options(selectinload(Material.concepts).selectinload(Concept.prerequisite_edges))
        )
        return self.db.scalars(stmt).first()

    def list_materials(self) -> list[Material]:
        stmt = select(Material).order_by(Material.created_at.desc())
        return list(self.db.scalars(stmt))

    # ── Concept ───────────────────────────────────────────────
    def add_concept(
        self,
        *,
        material_id: int,
        name: str,
        description: str,
        depth: int,
        embedding: list[float] | None,
    ) -> Concept:
        concept = Concept(
            material_id=material_id,
            name=name,
            description=description,
            depth=depth,
            embedding=embedding,
        )
        self.db.add(concept)
        self.db.flush()
        return concept

    def add_prerequisite(self, *, concept_id: int, prerequisite_concept_id: int) -> None:
        # 자기참조/중복 엣지는 무시 (그래프 무결성).
        if concept_id == prerequisite_concept_id:
            return
        edge = ConceptPrerequisite(
            concept_id=concept_id, prerequisite_concept_id=prerequisite_concept_id
        )
        self.db.add(edge)
        self.db.flush()
