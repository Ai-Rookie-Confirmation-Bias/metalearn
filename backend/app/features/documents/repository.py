"""[4.Repository] Document/Course/Concept/Edge DB 입출력."""
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.features.documents.models import Concept, ConceptEdge, Course, Document


class DocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_document(self, *, user_id: int, filename: str) -> Document:
        document = Document(user_id=user_id, filename=filename, status="processing")
        self.db.add(document)
        self.db.flush()
        return document

    def create_course(
        self, *, document_id: int, user_id: int, title: str, category: str | None = None
    ) -> Course:
        course = Course(
            document_id=document_id,
            user_id=user_id,
            title=title,
            category=category,
        )
        self.db.add(course)
        self.db.flush()
        return course

    def get_document(self, document_id: int) -> Document | None:
        return self.db.get(Document, document_id)

    def get_course(self, course_id: int) -> Course | None:
        stmt = (
            select(Course)
            .where(Course.id == course_id)
            .options(
                selectinload(Course.concepts).selectinload(Concept.prerequisite_edges),
                selectinload(Course.document),
            )
        )
        return self.db.scalars(stmt).first()

    def list_courses(self) -> list[Course]:
        stmt = (
            select(Course)
            .order_by(Course.created_at.desc())
            .options(selectinload(Course.document))
        )
        return list(self.db.scalars(stmt))

    def add_concept(
        self,
        *,
        course_id: int,
        name: str,
        description: str,
        depth_level: int,
        embedding: list[float] | None,
        source: str = "document",
        source_anchor: str | None = None,
    ) -> Concept:
        concept = Concept(
            course_id=course_id,
            name=name,
            description=description,
            depth_level=depth_level,
            embedding=embedding,
            source=source,
            source_anchor=source_anchor,
        )
        self.db.add(concept)
        self.db.flush()
        return concept

    def get_concept(self, concept_id: int) -> Concept | None:
        return self.db.get(Concept, concept_id)

    def find_nearest_concept(
        self, *, course_id: int, embedding: list[float]
    ) -> tuple[Concept, float] | None:
        """코스 내 최근접 개념과 코사인 유사도(1-거리)를 반환. 없으면 None."""
        dist = Concept.embedding.cosine_distance(embedding)
        stmt = (
            select(Concept, dist.label("dist"))
            .where(Concept.course_id == course_id, Concept.embedding.is_not(None))
            .order_by(dist)
            .limit(1)
        )
        row = self.db.execute(stmt).first()
        if row is None:
            return None
        concept, distance = row
        return concept, 1.0 - float(distance)

    def add_edge(
        self, *, from_concept_id: int, to_concept_id: int, kind: str = "prerequisite"
    ) -> None:
        if from_concept_id == to_concept_id:
            return
        self.db.add(
            ConceptEdge(
                from_concept_id=from_concept_id,
                to_concept_id=to_concept_id,
                kind=kind,
            )
        )
        self.db.flush()
