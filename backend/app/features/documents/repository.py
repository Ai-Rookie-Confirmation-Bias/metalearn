"""[4.Repository] Document/Course/Concept/Edge DB 입출력.

병합 2단계: parsing의 Integer 모델 대신 정본 UUID 모델
(materials.Document/DocChunk, seed.Course/Concept/ConceptEdge)을 사용한다.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased, selectinload

from app.features.materials.models import DocChunk, Document
from app.features.seed.models import Concept, ConceptEdge, Course


class DocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_document(self, *, user_id: uuid.UUID, filename: str) -> Document:
        document = Document(user_id=user_id, filename=filename, status="processing")
        self.db.add(document)
        self.db.flush()
        return document

    def create_course(
        self,
        *,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str,
        category: str | None = None,
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

    def get_document(self, document_id: uuid.UUID) -> Document | None:
        return self.db.get(Document, document_id)

    def get_course(self, course_id: uuid.UUID) -> Course | None:
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

    def add_chunks(
        self,
        *,
        document_id: uuid.UUID,
        chunks: list,
        embeddings: list[list[float] | None],
    ) -> list[DocChunk]:
        """청크(sectioning.Chunk) 목록을 doc_chunks 행으로 영속화."""
        rows: list[DocChunk] = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            row = DocChunk(
                document_id=document_id,
                chunk_index=i,
                content=chunk.text,
                embedding=embedding,
                element_from=chunk.el_from,
                element_to=chunk.el_to,
                heading=chunk.anchor,
                part_index=chunk.part,
                page_from=chunk.page_from,
                page_to=chunk.page_to,
            )
            self.db.add(row)
            rows.append(row)
        self.db.flush()
        return rows

    def add_concept(
        self,
        *,
        course_id: uuid.UUID,
        name: str,
        description: str,
        depth_level: int,
        embedding: list[float] | None,
        source: str = "book",  # 정본 규약: book | ai_prereq (MERGE_AGREEMENT)
        source_anchor: str | None = None,
        source_chunk_id: uuid.UUID | None = None,
        key: str | None = None,
    ) -> Concept:
        concept = Concept(
            course_id=course_id,
            name=name,
            description=description,
            depth_level=depth_level,
            embedding=embedding,
            source=source,
            source_anchor=source_anchor,
            source_chunk_id=source_chunk_id,
            key=key,
        )
        self.db.add(concept)
        self.db.flush()
        return concept

    def get_concept(self, concept_id: uuid.UUID) -> Concept | None:
        return self.db.get(Concept, concept_id)

    def find_nearest_concept(
        self, *, course_id: uuid.UUID, embedding: list[float]
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

    def find_similar_pairs(
        self, *, course_id: uuid.UUID, min_sim: float, limit: int
    ) -> list[tuple[Concept, Concept, float]]:
        """코스 내 임베딩 유사도 min_sim 이상인 개념쌍 (유사도 내림차순).

        일괄 dedup 패스(ISSUE-011)의 후보 수집용 — 판정은 LLM이 한다.
        """
        a, b = aliased(Concept), aliased(Concept)
        dist = a.embedding.cosine_distance(b.embedding)
        stmt = (
            select(a, b, dist.label("dist"))
            .where(
                a.course_id == course_id,
                b.course_id == course_id,
                a.id < b.id,
                a.embedding.is_not(None),
                b.embedding.is_not(None),
                dist <= 1.0 - min_sim,
            )
            .order_by(dist)
            .limit(limit)
        )
        return [
            (row_a, row_b, 1.0 - float(d))
            for row_a, row_b, d in self.db.execute(stmt).all()
        ]

    def merge_concepts(self, *, keep: Concept, drop: Concept) -> None:
        """drop의 에지를 keep으로 이관하고 drop을 삭제.

        자기참조가 되거나 keep에 이미 있는 (from,to,kind) 에지는 버린다
        (uq_concept_edge 충돌 방지). 진단/학습 데이터가 생기기 전
        (ingest 직후)에만 호출할 것 — concepts FK가 CASCADE라 이후에
        호출하면 학습 기록이 같이 지워진다.
        """
        touching = self.db.scalars(
            select(ConceptEdge).where(
                (ConceptEdge.from_concept_id == drop.id)
                | (ConceptEdge.to_concept_id == drop.id)
            )
        ).all()
        existing = {
            (e.from_concept_id, e.to_concept_id, e.kind)
            for e in self.db.scalars(
                select(ConceptEdge).where(
                    (ConceptEdge.from_concept_id == keep.id)
                    | (ConceptEdge.to_concept_id == keep.id)
                )
            )
        }
        for edge in touching:
            new_from = keep.id if edge.from_concept_id == drop.id else edge.from_concept_id
            new_to = keep.id if edge.to_concept_id == drop.id else edge.to_concept_id
            if new_from == new_to or (new_from, new_to, edge.kind) in existing:
                self.db.delete(edge)
            else:
                edge.from_concept_id, edge.to_concept_id = new_from, new_to
                existing.add((new_from, new_to, edge.kind))
        self.db.delete(drop)
        self.db.flush()

    def add_edge(
        self,
        *,
        from_concept_id: uuid.UUID,
        to_concept_id: uuid.UUID,
        kind: str = "prerequisite",
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
