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
from collections import Counter, defaultdict

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
from app.features.parsing.models import (
    Concept,
    ConceptLink,
    Document,
    DocSegment,
    MaterialRole,
)
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
        body_segments = self._body_segments_by_topic(
            concept_rows, body, body_ids, order=[t.source_topic_id for t in course.topics]
        )

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

        # 26이 만든 보강 자료의 개념. 뼈대 밖 문서라 load_tree가 안 가져온다.
        supplied = self._supplied(course, skip=set(concepts_by_topic))

        # **course_topics를 순회한다.** 사용자가 고친 목차가 학습 순서다.
        # source_topic_id로 원본 단원을 찾아 그 단원의 개념을 붙인다.
        for topic in course.topics:
            # 원본이 없는 단원은 뼈대 개념이 없다. `source`가 None일 때 사전을
            # 그냥 조회하면 **목차 배정에 실패한 고아 개념**(topic_id IS NULL)이
            # 딸려 온다 — 실측에서 AWS 코스의 단원 셋에 같은 고아 11개가 세 번
            # 똑같이 붙었다.
            source = topic.source_topic_id
            if source is None:
                tree.topics.append(
                    CourseTopicNode(
                        id=topic.id,
                        seq=topic.seq,
                        title=topic.title,
                        origin=topic.origin,
                        plan=topic.plan,
                        source_topic_id=None,
                    )
                )
                continue

            if source in supplied:
                # 보강 단원(26이 만든 것). 조각이 없고 명세뿐이다 — 학습층이
                # 거기서 설명을 생성한다. 쪽수도 원문도 없는 게 정상이다.
                tree.topics.append(
                    CourseTopicNode(
                        id=topic.id,
                        seq=topic.seq,
                        title=topic.title,
                        origin=topic.origin,
                        plan=topic.plan,
                        source_topic_id=source,
                        concepts=supplied[source],
                    )
                )
                continue

            own = [
                _to_segment(s, document_id=skeleton_id, filename=filename)
                for s in segments_by_topic.get(source, [])
            ]
            # 쪽 범위는 **뼈대 기준**이다. 본문 자료의 쪽수를 섞으면 "지금 교재
            # 몇 쪽" 표시가 두 책을 오간다.
            lo, hi = _page_range(own)
            tree.topics.append(
                CourseTopicNode(
                    id=topic.id,
                    seq=topic.seq,
                    title=topic.title,
                    origin=topic.origin,
                    plan=topic.plan,
                    source_topic_id=source,
                    page_from=lo,
                    page_to=hi,
                    concepts=[to_concept(c) for c in concepts_by_topic.get(source, [])],
                    segments=own + body_segments.get(source, []),
                )
            )

        tree.total_concepts = len(concept_rows)
        tree.linked_concepts = sum(1 for c in concept_rows if body.get(c.id))
        _log.info(
            "코스 트리: %s — 개념 %d개 중 %d개에 본문이 붙음",
            course.title, tree.total_concepts, tree.linked_concepts,
        )
        return tree

    def _supplied(
        self, course: Course, *, skip: set[uuid.UUID | None]
    ) -> dict[uuid.UUID, list[CourseConceptOut]]:
        """26이 만든 보강 단원의 개념. `{doc_topic_id: [개념...]}`.

        `load_tree(skeleton_id)`는 뼈대 문서 하나만 읽으므로 보강 자료의 개념은
        안 들어온다. 그대로 두면 끼운 단원이 **빈 껍데기로 나간다** — 목차에는
        보이는데 열면 아무것도 없다.

        `skip`으로 뼈대 단원을 걸러 낸다. 사용자가 뼈대 안의 단원을 복제해
        `origin=inserted`로 만들 수도 있어서, `origin`이 아니라 **원본이 어느
        문서 것인가**로 갈라야 한다.
        """
        sources = [
            t.source_topic_id
            for t in course.topics
            if t.source_topic_id is not None and t.source_topic_id not in skip
        ]
        if not sources:
            return {}

        rows = self.db.execute(
            select(Concept, Document.filename)
            .join(Document, Document.id == Concept.document_id)
            .where(Concept.topic_id.in_(sources))
            .order_by(Concept.topic_id, Concept.name)
        ).all()

        out: dict[uuid.UUID, list[CourseConceptOut]] = defaultdict(list)
        for concept, filename in rows:
            out[concept.topic_id].append(
                CourseConceptOut(
                    id=concept.id,
                    name=concept.name,
                    definition=concept.definition,
                    source=concept.source,
                    global_key=concept.global_key,
                    document_id=concept.document_id,
                    filename=filename,
                    # 조각이 없다. 원문도 근거도 없는 게 이 단원의 정의다.
                )
            )
        return dict(out)

    def _body_segments_by_topic(
        self,
        concept_rows: list[Concept],
        body: dict[uuid.UUID, list[BodyRefOut]],
        body_ids: list[uuid.UUID],
        *,
        order: list[uuid.UUID | None],
    ) -> dict[uuid.UUID, list[BodySegmentOut]]:
        """본문 자료의 조각을 **통째로** 단원에 싣는다.

        왜 조각 단위인가 — 화면을 만드는 건 학습 층이다. 우리가 개념 언저리만
        잘라 보내면 그쪽이 쓸 수 있는 재료가 줄어든다. 실측에서 개념 자리만
        창으로 잘랐더니 교재 76,839자 중 25,627자(33%)만 넘어갔다. 자르기는
        받는 쪽 `split_by_concepts`가 원래 하던 일이다.

        배정은 두 단계다:

          ① 개념 링크가 가리키는 조각 → 그 개념이 속한 단원 (표가 갈리면 다수결)
          ② 아무 개념도 안 가리키는 조각 → **앞 조각의 단원**

        ②의 근거는 책이 순서대로라는 것뿐이다. 실측(필기 뼈대 + 실기 본문)에서
        배정이 거의 단조로웠다 — 조각 0~5→단원0·1, 6~8→단원2, 9~11→단원3,
        13~18→단원4. 비어 있던 건 조각 12 하나였고 앞뒤가 단원3·4였다.
        앞을 택한다: 책은 앞 내용의 연장으로 흐른다.
        """
        if not body_ids:
            return {}

        rank = {tid: i for i, tid in enumerate(order) if tid is not None}
        topic_of_concept = {c.id: c.topic_id for c in concept_rows}

        # ① 링크 다수결. 조각 하나가 여러 단원에서 불릴 수 있다.
        votes: dict[uuid.UUID, Counter] = defaultdict(Counter)
        for concept_id, refs in body.items():
            topic_id = topic_of_concept.get(concept_id)
            if topic_id is None:
                continue
            for ref in refs:
                for seg in ref.segments:
                    votes[seg.id][topic_id] += 1

        def winner(segment_id: uuid.UUID) -> uuid.UUID | None:
            counts = votes.get(segment_id)
            if not counts:
                return None
            top = max(counts.values())
            # 동수면 앞 단원. 뒤로 미루면 선수 개념이 나중에 나온다.
            return min(
                (t for t, n in counts.items() if n == top),
                key=lambda t: rank.get(t, 10**6),
            )

        out: dict[uuid.UUID, list[BodySegmentOut]] = defaultdict(list)
        for offset, document_id in enumerate(body_ids):
            document = self.repo.get_document(document_id)
            name = document.filename if document else ""
            rows = list(
                self.db.scalars(
                    select(DocSegment)
                    .where(DocSegment.document_id == document_id)
                    .order_by(DocSegment.seq)
                )
            )
            assigned = [winner(row.id) for row in rows]
            # ② 빈 자리를 앞에서 끌어온다. 맨 앞이 비었으면 뒤에서 한 번 당긴다.
            last: uuid.UUID | None = None
            for i, topic_id in enumerate(assigned):
                if topic_id is None:
                    assigned[i] = last
                else:
                    last = topic_id
            nxt: uuid.UUID | None = None
            for i in range(len(assigned) - 1, -1, -1):
                if assigned[i] is None:
                    assigned[i] = nxt
                else:
                    nxt = assigned[i]

            for row, topic_id in zip(rows, assigned):
                if topic_id is None:
                    continue  # 이 자료에 붙은 개념이 하나도 없다
                out[topic_id].append(
                    _to_segment(
                        row,
                        document_id=document_id,
                        filename=name,
                        role=MaterialRole.BODY.value,
                        # 받는 쪽이 seq로 정렬한다. 뼈대(0~n) 뒤에 오도록 민다 —
                        # 섞이면 뼈대가 정한 학습 순서가 흐트러진다.
                        seq=_BODY_SEQ_BASE + offset * _BODY_SEQ_STRIDE + row.seq,
                    )
                )
        return dict(out)

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


# 본문 조각의 seq를 미는 값. 받는 쪽이 `segments`를 seq로 정렬하므로
# 뼈대(0~n)와 겹치면 안 된다. STRIDE는 본문 자료 하나당 조각 상한이다.
_BODY_SEQ_BASE = 1000
_BODY_SEQ_STRIDE = 1000


def _page_range(segments: list[BodySegmentOut]) -> tuple[int | None, int | None]:
    """조각들이 걸친 쪽 범위. 값이 하나도 없으면 (None, None)."""
    lows = [s.page_from for s in segments if s.page_from is not None]
    highs = [s.page_to for s in segments if s.page_to is not None]
    return (min(lows) if lows else None, max(highs) if highs else None)


def _to_segment(
    row: DocSegment,
    *,
    document_id: uuid.UUID | None = None,
    filename: str | None = None,
    role: str = MaterialRole.SKELETON.value,
    seq: int | None = None,
) -> BodySegmentOut:
    """조각 하나를 그대로. `seq`를 주면 그 값으로 덮는다(단원 안 정렬용)."""
    return BodySegmentOut(
        id=row.id,
        seq=row.seq if seq is None else seq,
        heading=row.heading,
        content=row.content,
        page_from=row.page_from,
        page_to=row.page_to,
        document_id=document_id if document_id is not None else row.document_id,
        filename=filename,
        role=role,
    )
