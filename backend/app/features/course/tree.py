"""코스 트리 조립 — 뼈대 목차에 본문 자료의 설명을 얹는다.

문서 트리(`ParsingService.get_tree`)와 무엇이 다른가:

    문서 트리   책 한 권 안에서만 본다. 목차 → 조각 → 개념 → 근거
    코스 트리   코스에 묶인 자료 전부를 본다. 뼈대 목차 → 개념 → **다른 자료의 설명**

**목차는 course_topics를 쓴다.** doc_topics가 아니다 — 사용자가 제목을 바꾸고
순서를 옮기고 보강 단원을 끼울 수 있어야 하고, 그 복사본이 course_topics다.
원본과의 연결은 `source_topic_id`로 유지한다.

개념은 뼈대 자료 것을 그대로 쓰고, `concept_links`를 타고 본문 자료의 개념과
그 개념이 설명되는 조각을 끌어온다.
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.features.course.models import Course
from app.features.course.schemas import (
    BodyRefOut,
    BodySegmentOut,
    CourseConceptOut,
    CourseTopicNode,
    CourseTree,
)
from app.features.parsing.models import Concept, ConceptLink, Document, DocSegment
from app.features.parsing.repository import ParsingRepository
from app.features.parsing.service import _evidence_of

_log = logging.getLogger("uvicorn.error")


class CourseTreeBuilder:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ParsingRepository(db)

    def build(
        self,
        course: Course,
        *,
        skeleton_id: uuid.UUID | None,
        body_ids: list[uuid.UUID],
    ) -> CourseTree:
        tree = CourseTree(
            course_id=course.id,
            title=course.title,
            skeleton_document_id=skeleton_id,
            body_document_ids=body_ids,
        )
        if skeleton_id is None:
            return tree

        topic_rows, segment_rows, concept_rows, edge_rows = self.repo.load_tree(
            skeleton_id
        )
        seq_of_segment = {s.id: s.seq for s in segment_rows}
        pages_of_segment = {s.seq: (s.page_from, s.page_to) for s in segment_rows}
        sentences = self.repo.load_sentences(skeleton_id)

        prereqs: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        for edge in edge_rows:
            if edge.kind == "prerequisite":
                prereqs[edge.from_concept_id].append(edge.to_concept_id)

        concepts_by_topic: dict[uuid.UUID | None, list[Concept]] = defaultdict(list)
        for row in concept_rows:
            concepts_by_topic[row.topic_id].append(row)

        segments_by_topic: dict[uuid.UUID | None, list[DocSegment]] = defaultdict(list)
        for row in segment_rows:
            segments_by_topic[row.topic_id].append(row)

        body = self._body_refs([c.id for c in concept_rows], body_ids)
        skeleton_doc = self.repo.get_document(skeleton_id)
        filename = skeleton_doc.filename if skeleton_doc else ""

        def to_concept(row: Concept) -> CourseConceptOut:
            return CourseConceptOut(
                id=row.id,
                name=row.name,
                definition=row.definition,
                source=row.source,
                global_key=row.global_key,
                document_id=skeleton_id,
                filename=filename,
                segment_seqs=sorted(
                    seq_of_segment[l.segment_id]
                    for l in row.segment_links
                    if l.segment_id in seq_of_segment
                ),
                prerequisite_ids=prereqs.get(row.id, []),
                evidence=[
                    e.model_dump()
                    for e in _evidence_of(row, sentences, pages_of_segment)
                ],
                body=body.get(row.id, []),
            )

        # **course_topics를 순회한다.** 사용자가 고친 목차가 학습 순서다.
        # source_topic_id로 원본 단원을 찾아 그 단원의 개념을 붙인다.
        for topic in course.topics:
            source = topic.source_topic_id
            tree.topics.append(
                CourseTopicNode(
                    id=topic.id,
                    seq=topic.seq,
                    title=topic.title,
                    origin=topic.origin,
                    plan=topic.plan,
                    source_topic_id=source,
                    concepts=[to_concept(c) for c in concepts_by_topic.get(source, [])],
                    segments=[
                        _to_segment(s) for s in segments_by_topic.get(source, [])
                    ],
                )
            )

        tree.total_concepts = len(concept_rows)
        tree.linked_concepts = sum(1 for c in concept_rows if body.get(c.id))
        _log.info(
            "코스 트리: %s — 개념 %d개 중 %d개에 본문이 붙음",
            course.title, tree.total_concepts, tree.linked_concepts,
        )
        return tree

    def _body_refs(
        self, concept_ids: list[uuid.UUID], body_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[BodyRefOut]]:
        """뼈대 개념 → 본문 자료의 설명. `concept_links`가 무방향이라 양쪽을 본다."""
        if not concept_ids or not body_ids:
            return {}

        links = list(
            self.db.scalars(
                select(ConceptLink).where(
                    or_(
                        ConceptLink.concept_a_id.in_(concept_ids),
                        ConceptLink.concept_b_id.in_(concept_ids),
                    )
                )
            )
        )
        if not links:
            return {}

        wanted = set(concept_ids)
        partners: dict[uuid.UUID, list[tuple[uuid.UUID, ConceptLink]]] = defaultdict(list)
        partner_ids: set[uuid.UUID] = set()
        for row in links:
            # 무방향이라 어느 쪽이 뼈대인지 여기서 가른다.
            if row.concept_a_id in wanted:
                mine, theirs = row.concept_a_id, row.concept_b_id
            else:
                mine, theirs = row.concept_b_id, row.concept_a_id
            if theirs in wanted:
                continue  # 같은 자료 안 연결. 여기서는 쓰지 않는다
            partners[mine].append((theirs, row))
            partner_ids.add(theirs)

        matched = {
            c.id: c
            for c in self.db.scalars(
                select(Concept)
                .where(
                    Concept.id.in_(partner_ids),
                    Concept.document_id.in_(body_ids),
                )
                .options(selectinload(Concept.segment_links))
            )
        }
        filenames = dict(
            self.db.execute(
                select(Document.id, Document.filename).where(
                    Document.id.in_(body_ids)
                )
            ).all()
        )
        segments = self._segments_of(matched.values())

        out: dict[uuid.UUID, list[BodyRefOut]] = {}
        for concept_id, items in partners.items():
            refs = []
            for partner_id, row in items:
                partner = matched.get(partner_id)
                if partner is None:
                    continue
                refs.append(
                    BodyRefOut(
                        concept_id=partner.id,
                        document_id=partner.document_id,
                        filename=filenames.get(partner.document_id, ""),
                        name=partner.name,
                        definition=partner.definition,
                        similarity=round(row.similarity, 4),
                        kind=row.kind,
                        verified_by=row.verified_by,
                        segments=segments.get(partner.id, []),
                    )
                )
            if refs:
                # 같은 개념이 본문 자료 여럿에 있으면 가까운 쪽을 먼저 보여준다.
                refs.sort(key=lambda r: -r.similarity)
                out[concept_id] = refs
        return out

    def _segments_of(self, concepts) -> dict[uuid.UUID, list[BodySegmentOut]]:
        """본문 개념이 실제로 설명되는 조각들. 이게 화면의 본문이 된다."""
        wanted: set[uuid.UUID] = set()
        for concept in concepts:
            wanted.update(l.segment_id for l in concept.segment_links if l.segment_id)
        if not wanted:
            return {}

        rows = {
            s.id: s
            for s in self.db.scalars(
                select(DocSegment).where(DocSegment.id.in_(wanted))
            )
        }
        out: dict[uuid.UUID, list[BodySegmentOut]] = {}
        for concept in concepts:
            items = [
                _to_segment(rows[l.segment_id])
                for l in concept.segment_links
                if l.segment_id in rows
            ]
            if items:
                items.sort(key=lambda s: s.seq)
                out[concept.id] = items
        return out


def _to_segment(row: DocSegment) -> BodySegmentOut:
    return BodySegmentOut(
        id=row.id,
        seq=row.seq,
        heading=row.heading,
        content=row.content,
        page_from=row.page_from,
        page_to=row.page_to,
    )
