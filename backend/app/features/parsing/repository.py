"""[Repository] DB 접근만. 비즈니스 로직 없음.

파이프라인 판정은 전부 pipeline/에 있고, 여기는 읽고 쓰는 일만 한다.
"""
from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased, defer, selectinload

from app.features.parsing.models import (
    Concept,
    ConceptEdge,
    ConceptSegment,
    DocFigure,
    Document,
    DocSegment,
    DocTopic,
    SegmentSentence,
    UserDocument,
)
from app.features.parsing.schemas import FigureDraft, Segment


class ParsingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── 문서 ──────────────────────────────────────────────────────

    def get_document(self, document_id: uuid.UUID) -> Document | None:
        return self.db.get(Document, document_id)

    def find_by_fingerprint(self, fingerprint: str) -> Document | None:
        """같은 파일이 이미 파싱돼 있는지. 문서가 공용이라 가능한 조회다."""
        return self.db.scalar(
            select(Document).where(Document.fingerprint == fingerprint)
        )

    def create_document(
        self, *, fingerprint: str, filename: str, source_format: str,
        storage_path: str | None = None,
    ) -> Document:
        document = Document(
            fingerprint=fingerprint,
            filename=filename,
            source_format=source_format,
            storage_path=storage_path,
        )
        self.db.add(document)
        self.db.flush()
        return document

    def link_user(
        self, *, user_id: uuid.UUID, document_id: uuid.UUID, role: str
    ) -> UserDocument:
        """소유 관계 등록. 이미 있으면 역할만 갱신한다."""
        link = self.db.scalar(
            select(UserDocument).where(
                UserDocument.user_id == user_id,
                UserDocument.document_id == document_id,
            )
        )
        if link is None:
            link = UserDocument(user_id=user_id, document_id=document_id, role=role)
            self.db.add(link)
        else:
            link.role = role
        return link

    def clear_parsed(self, document_id: uuid.UUID) -> None:
        """이전 파싱 산출물을 지운다. 재파싱 전에 반드시 호출할 것.

        조각·목차의 seq에 유니크 제약이 걸려 있어, 남겨두면 두 번째 실행이
        곧바로 충돌한다. 문서 행 자체와 소유 관계(user_documents)는 유지한다 —
        사용자가 다시 올릴 필요는 없다.
        """
        for model in (DocFigure, ConceptEdge, Concept, DocSegment, DocTopic):
            self.db.query(model).filter(model.document_id == document_id).delete(
                synchronize_session=False
            )
        self.db.flush()

    # ── 목차 · 조각 ───────────────────────────────────────────────

    def add_topics(
        self, *, document_id: uuid.UUID, titles: Sequence[tuple[int, str]]
    ) -> dict[int, DocTopic]:
        """{목차 seq: DocTopic} 반환."""
        rows = {
            seq: DocTopic(document_id=document_id, seq=seq, title=title)
            for seq, title in titles
        }
        self.db.add_all(rows.values())
        self.db.flush()
        return rows

    def add_segments(
        self,
        *,
        document_id: uuid.UUID,
        segments: Sequence[Segment],
        embeddings: Sequence[list[float]] | None = None,
    ) -> dict[int, DocSegment]:
        """{조각 seq: DocSegment} 반환. topic_id는 아직 비어 있다."""
        vectors = list(embeddings or [])
        rows: dict[int, DocSegment] = {}
        for i, segment in enumerate(segments):
            rows[segment.seq] = DocSegment(
                document_id=document_id,
                seq=segment.seq,
                content=segment.content,
                heading=segment.heading,
                element_from=segment.element_from,
                element_to=segment.element_to,
                page_from=segment.page_from,
                page_to=segment.page_to,
                char_count=segment.char_count,
                embedding=vectors[i] if i < len(vectors) else None,
            )
        self.db.add_all(rows.values())
        self.db.flush()
        return rows

    def add_sentences(
        self, *, sentences_by_seq: dict[int, list], segment_rows: dict[int, DocSegment]
    ) -> int:
        """문장 앵커 저장. 반환: 저장한 문장 수."""
        rows = [
            SegmentSentence(
                segment_id=segment_rows[seq].id,
                seq=s.seq,
                text=s.text,
                char_start=s.char_start,
                char_end=s.char_end,
            )
            for seq, sentences in sentences_by_seq.items()
            if seq in segment_rows
            for s in sentences
        ]
        self.db.add_all(rows)
        self.db.flush()
        return len(rows)

    @staticmethod
    def assign_topic(segment: DocSegment, topic: DocTopic) -> None:
        segment.topic_id = topic.id

    @staticmethod
    def set_topic_pages(topic: DocTopic, segments: Sequence[DocSegment]) -> None:
        """목차의 페이지 범위를 소속 조각들로부터 채운다."""
        pages = [
            p for s in segments for p in (s.page_from, s.page_to) if p is not None
        ]
        if pages:
            topic.page_from, topic.page_to = min(pages), max(pages)

    # ── 그림 ──────────────────────────────────────────────────────

    def add_figures(
        self,
        *,
        document_id: uuid.UUID,
        figures: Sequence[FigureDraft],
        located: dict[int, tuple[DocSegment, int]] | None = None,
    ) -> list[DocFigure]:
        """located: {element_id: (조각 행, 조각 본문 내 char offset)}"""
        located = located or {}
        rows = [
            DocFigure(
                document_id=document_id,
                segment_id=(
                    located[f.element_id][0].id if f.element_id in located else None
                ),
                char_offset=(
                    located[f.element_id][1] if f.element_id in located else 0
                ),
                page=f.page,
                element_id=f.element_id,
                category=f.category,
                caption=f.caption,
                context_text=f.context_text,
                needs_vision=f.needs_vision,
                mime=f.mime,
                data=f.data,
            )
            for f in figures
        ]
        self.db.add_all(rows)
        self.db.flush()
        return rows

    # ── 개념 ──────────────────────────────────────────────────────

    def add_concept(
        self,
        *,
        document_id: uuid.UUID,
        topic_id: uuid.UUID | None,
        name: str,
        normalized_name: str,
        definition: str | None,
        global_key: str | None,
        source: str,
        embedding: list[float] | None,
        evidence_sentences: list[list[int]] | None = None,
    ) -> Concept:
        concept = Concept(
            document_id=document_id,
            topic_id=topic_id,
            name=name,
            normalized_name=normalized_name,
            definition=definition,
            global_key=global_key,
            source=source,
            embedding=embedding,
            evidence_sentences=evidence_sentences or [],
        )
        self.db.add(concept)
        self.db.flush()
        return concept

    def link_concept_segment(
        self, *, concept_id: uuid.UUID, segment_id: uuid.UUID
    ) -> bool:
        """⭐ 개념 ↔ 조각 연결. 같은 개념이 여러 조각에 나오면 전부 쌓인다.

        기존 구현은 concepts.source_chunk_id 단수 컬럼이라 첫 등장만 남았다.

        새로 만들었으면 True. 저장은 2-pass라 같은 쌍이 두 번 들어오는데,
        그때 링크 수가 부풀지 않게 반환값으로 구분한다.
        """
        exists = self.db.scalar(
            select(ConceptSegment.id).where(
                ConceptSegment.concept_id == concept_id,
                ConceptSegment.segment_id == segment_id,
            )
        )
        if exists is not None:
            return False
        self.db.add(ConceptSegment(concept_id=concept_id, segment_id=segment_id))
        self.db.flush()
        return True

    def add_edge(
        self,
        *,
        document_id: uuid.UUID,
        from_concept_id: uuid.UUID,
        to_concept_id: uuid.UUID,
        kind: str = "prerequisite",
    ) -> None:
        self.db.add(
            ConceptEdge(
                document_id=document_id,
                from_concept_id=from_concept_id,
                to_concept_id=to_concept_id,
                kind=kind,
            )
        )

    # ── 중복 판정 (10단계) ────────────────────────────────────────

    def find_similar_pairs(
        self, *, document_id: uuid.UUID, min_sim: float, limit: int
    ) -> list[tuple[Concept, Concept, float]]:
        """임베딩 유사도가 min_sim 이상인 개념쌍 (유사도 내림차순).

        후보 수집만 한다 — 같은지 아닌지는 LLM이 판정한다.
        """
        a, b = aliased(Concept), aliased(Concept)
        dist = a.embedding.cosine_distance(b.embedding)
        stmt = (
            select(a, b, dist.label("dist"))
            .where(
                a.document_id == document_id,
                b.document_id == document_id,
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

    def search_concepts(
        self,
        *,
        embedding: list[float],
        limit: int,
        document_ids: list[uuid.UUID] | None = None,
        min_sim: float = 0.0,
    ) -> list[tuple[Concept, float]]:
        """개념 임베딩 최근접 검색. **문서 경계를 넘는다.**

        find_similar_pairs는 한 문서 안의 중복을 찾는 용도라 문서 경계를 넘지
        못한다. 자료 간 개념 매칭(PPT의 개념 ↔ 교재의 설명)과 외부 조달은
        문서를 넘어야 하므로 별도 조회가 필요하다.

        개념 벡터는 query 모델로 만들었으므로 검색어도 query로 임베딩해야
        한다 — passage로 넣으면 실측에서 점수가 0.566 → 0.399로 떨어졌다.
        """
        distance = Concept.embedding.cosine_distance(embedding)
        stmt = (
            select(Concept, distance.label("dist"))
            .where(Concept.embedding.is_not(None), distance <= 1.0 - min_sim)
            .options(selectinload(Concept.segment_links))
            .order_by(distance)
            .limit(limit)
        )
        if document_ids:
            stmt = stmt.where(Concept.document_id.in_(document_ids))
        return [
            (concept, 1.0 - float(dist))
            for concept, dist in self.db.execute(stmt).all()
        ]

    def get_concept(self, concept_id: uuid.UUID) -> Concept | None:
        return self.db.get(Concept, concept_id)

    def merge_concepts(self, *, keep: Concept, drop: Concept) -> int:
        """drop을 keep에 합치고 삭제한다. 반환: 새로 넘어온 원문 링크 수.

        ⭐ **원문 출처를 먼저 이관한다.** concept_segments가 concept_id에
        CASCADE로 걸려 있어, 그냥 지우면 drop이 가리키던 원문 링크가 통째로
        사라진다. 기존 구현이 정확히 이 지점에서 정보를 잃었다 — 개념이
        6p·11p·15p에서 나와 셋으로 갈렸다가 하나로 합쳐지면 6p만 남았다.
        """
        moved = 0
        existing_segments = {
            link.segment_id
            for link in self.db.scalars(
                select(ConceptSegment).where(ConceptSegment.concept_id == keep.id)
            )
        }
        for link in self.db.scalars(
            select(ConceptSegment).where(ConceptSegment.concept_id == drop.id)
        ):
            if link.segment_id in existing_segments:
                self.db.delete(link)  # 이미 keep이 가진 원문 — 중복 행만 정리
            else:
                link.concept_id = keep.id
                existing_segments.add(link.segment_id)
                moved += 1

        # 엣지 이관 — 자기참조와 이미 있는 (from, to, kind)는 버린다.
        touching = self.db.scalars(
            select(ConceptEdge).where(
                (ConceptEdge.from_concept_id == drop.id)
                | (ConceptEdge.to_concept_id == drop.id)
            )
        ).all()
        existing_edges = {
            (e.from_concept_id, e.to_concept_id, e.kind)
            for e in self.db.scalars(
                select(ConceptEdge).where(
                    (ConceptEdge.from_concept_id == keep.id)
                    | (ConceptEdge.to_concept_id == keep.id)
                )
            )
        }
        for edge in touching:
            new_from = (
                keep.id if edge.from_concept_id == drop.id else edge.from_concept_id
            )
            new_to = keep.id if edge.to_concept_id == drop.id else edge.to_concept_id
            if new_from == new_to or (new_from, new_to, edge.kind) in existing_edges:
                self.db.delete(edge)
            else:
                edge.from_concept_id, edge.to_concept_id = new_from, new_to
                existing_edges.add((new_from, new_to, edge.kind))

        # 메타데이터도 좋은 쪽을 남긴다.
        if keep.source == "ai_prereq" and drop.source == "book":
            keep.source = "book"
            keep.definition = drop.definition
        if keep.topic_id is None:
            keep.topic_id = drop.topic_id
        if not keep.global_key:
            keep.global_key = drop.global_key
        # 근거 문장도 원문 링크와 같은 이유로 합친다 — 버리면 병합된 쪽의
        # "33p 이 문장"이 통째로 사라진다.
        merged_evidence = list(keep.evidence_sentences or [])
        for pair in drop.evidence_sentences or []:
            if pair not in merged_evidence:
                merged_evidence.append(pair)
        keep.evidence_sentences = merged_evidence

        self.db.delete(drop)
        self.db.flush()
        return moved

    # ── 조회 ──────────────────────────────────────────────────────

    def load_sentences(
        self, document_id: uuid.UUID
    ) -> dict[tuple[int, int], SegmentSentence]:
        """{(조각 seq, 문장 seq): 문장}. 개념의 근거를 원문 좌표로 푸는 데 쓴다.

        concepts.evidence_sentences가 [[조각 seq, 문장 seq], …]로 저장돼 있어
        이 형태여야 한 번의 조회로 전부 풀린다.
        """
        rows = self.db.execute(
            select(DocSegment.seq, SegmentSentence)
            .join(SegmentSentence, SegmentSentence.segment_id == DocSegment.id)
            .where(DocSegment.document_id == document_id)
        ).all()
        return {(seq, sentence.seq): sentence for seq, sentence in rows}

    def count_sentences(self, document_id: uuid.UUID) -> dict[uuid.UUID, int]:
        """{조각 id: 문장 수}"""
        rows = self.db.execute(
            select(SegmentSentence.segment_id, func.count())
            .join(DocSegment, DocSegment.id == SegmentSentence.segment_id)
            .where(DocSegment.document_id == document_id)
            .group_by(SegmentSentence.segment_id)
        ).all()
        return {segment_id: count for segment_id, count in rows}

    def list_figures(self, document_id: uuid.UUID) -> list[DocFigure]:
        """이미지 바이트는 빼고 메타만. 트리 응답에 수 MB를 실으면 안 된다."""
        return list(
            self.db.scalars(
                select(DocFigure)
                .where(DocFigure.document_id == document_id)
                .order_by(DocFigure.page, DocFigure.element_id)
                .options(defer(DocFigure.data))
            )
        )

    def load_tree(self, document_id: uuid.UUID) -> tuple[
        list[DocTopic], list[DocSegment], list[Concept], list[ConceptEdge]
    ]:
        """문서 전체 구조를 한 번에 읽어온다."""
        topics = list(
            self.db.scalars(
                select(DocTopic)
                .where(DocTopic.document_id == document_id)
                .order_by(DocTopic.seq)
            )
        )
        segments = list(
            self.db.scalars(
                select(DocSegment)
                .where(DocSegment.document_id == document_id)
                .order_by(DocSegment.seq)
            )
        )
        concepts = list(
            self.db.scalars(
                select(Concept)
                .where(Concept.document_id == document_id)
                .options(selectinload(Concept.segment_links))
                .order_by(Concept.name)
            )
        )
        edges = list(
            self.db.scalars(
                select(ConceptEdge).where(ConceptEdge.document_id == document_id)
            )
        )
        return topics, segments, concepts, edges
