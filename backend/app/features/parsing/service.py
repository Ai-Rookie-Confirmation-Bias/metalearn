"""파싱 오케스트레이션 — 단계 호출 순서와 상태 전이만.

**로직은 여기 두지 않는다.** 판정과 변환은 전부 pipeline/에 있다.
기존 구현의 service.py는 806줄에 추출·정제·임베딩·저장이 다 들어 있어
단계 하나를 따로 테스트할 수 없었고, 중간이 깨졌을 때 어디인지 알기 어려웠다.
"""
from __future__ import annotations

import hashlib
import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.features.parsing import repository as repo_module
from app.features.parsing.adapters import document_parse
from app.features.parsing.models import DocStatus, DocTopic, MaterialRole
from app.features.parsing.pipeline import (
    concepts,
    dedup,
    density,
    embed,
    figures,
    normalize,
    persist,
    refine,
    segment,
    sentences,
    topics,
)
from app.features.parsing.schemas import (
    ConceptHitOut,
    ConceptOut,
    DocumentOut,
    EvidenceOut,
    FigureOut,
    DocumentTree,
    SegmentOut,
    TopicOut,
)

_log = logging.getLogger("uvicorn.error")


class ParsingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = repo_module.ParsingRepository(db)

    # ── 업로드 ────────────────────────────────────────────────────

    def register(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        user_id: uuid.UUID | None = None,
        role: str = MaterialRole.SKELETON.value,
    ) -> tuple[uuid.UUID, bool]:
        """문서를 등록한다. 반환: (document_id, 새로 파싱해야 하는가).

        문서가 공용이므로 지문이 같으면 이미 파싱된 결과를 그대로 쓴다 —
        같은 교재를 N명이 올려도 파싱은 1회다.
        """
        fingerprint = hashlib.sha256(file_bytes).hexdigest()
        existing = self.repo.find_by_fingerprint(fingerprint)

        if existing is not None:
            if user_id is not None:
                self.repo.link_user(
                    user_id=user_id, document_id=existing.id, role=role
                )
                self.db.commit()
            # 아직 시작 안 했거나 실패한 것만 다시 돌린다.
            # 진행 중인 문서를 또 돌리면 같은 파이프라인이 겹쳐 실행된다.
            needs_parse = existing.status in (
                DocStatus.PENDING.value,
                DocStatus.FAILED.value,
            )
            _log.info(
                "문서 재사용: %s (지문 일치, 상태 %s, 재파싱 %s)",
                filename, existing.status, needs_parse,
            )
            return existing.id, needs_parse

        source_format, _ = document_parse.detect_format(filename)
        document = self.repo.create_document(
            fingerprint=fingerprint,
            filename=filename,
            source_format=source_format,
        )
        if user_id is not None:
            self.repo.link_user(
                user_id=user_id, document_id=document.id, role=role
            )
        self.db.commit()
        return document.id, True

    # ── 파이프라인 ────────────────────────────────────────────────

    async def run(self, document_id: uuid.UUID, file_bytes: bytes) -> None:
        """1 → 11단계. 실패하면 어느 단계에서 죽었는지 상태에 남는다."""
        document = self.repo.get_document(document_id)
        if document is None:
            raise ValueError(f"문서를 찾을 수 없습니다: {document_id}")

        def stage(name: DocStatus) -> None:
            document.status = name.value
            self.db.commit()

        try:
            await self._run_stages(document, file_bytes, stage)
        except Exception as exc:  # noqa: BLE001 — 실패 사유를 남기고 다시 던진다
            self.db.rollback()
            document = self.repo.get_document(document_id)
            if document is not None:
                document.status = DocStatus.FAILED.value
                document.error = f"{type(exc).__name__}: {exc}"[:2000]
                self.db.commit()
            _log.exception("파싱 실패: %s", document_id)
            raise

    async def _run_stages(self, document, file_bytes: bytes, stage) -> None:
        # 0. 이전 산출물 정리 (실패 후 재시도 경로).
        # error도 반드시 지운다 — 안 지우면 재시도로 성공한 문서가 ready인데
        # 지난번 실패 사유를 계속 달고 있게 된다.
        self.repo.clear_parsed(document.id)
        document.error = None

        # 1. Document Parse ─────────────────────────────────────────
        stage(DocStatus.PARSING)
        markdown, elements = await document_parse.parse(file_bytes, document.filename)
        document.raw_markdown = markdown
        self.db.commit()

        # 2. 그림 분리 (elements에서 base64를 떼어낸다 — 부수효과) ────
        figure_drafts = figures.extract(elements)

        # 2.5. 정규화 (제어문자 → 장식) ─────────────────────────────
        # 정제보다 앞이어야 한다 — 4단계가 LLM에 텍스트를 보내고 7단계가
        # 본문 단원 표기를 문자열로 매칭한다. 그림 분리 뒤여야 base64를
        # 이미 떼어낸 상태라 헛일이 없다.
        elements, _ = normalize.normalize(elements)
        elements, _ = normalize.clean(elements)

        # 3~4. 정제 (규칙 → LLM 스캔) ──────────────────────────────
        stage(DocStatus.REFINING)
        refined = refine.apply_rules(elements)
        await refine.apply_scan(refined)
        # 목차 페이지는 본문에서 빼되(removed=toc) 버리지는 않는다 —
        # 저자가 직접 나눈 단원 구분이라 7단계의 정답지가 된다.
        toc = refine.extract_toc(refined)
        page_sections = refine.extract_page_sections(refined)
        body_sections = refine.extract_body_sections(refined)
        document.refined_elements = {
            "elements": refined, "toc": toc,
            "page_sections": page_sections, "body_sections": body_sections,
        }
        self.db.commit()

        # 5. 조각 만들기 ────────────────────────────────────────────
        stage(DocStatus.SEGMENTING)
        segments = segment.build(
            refined,
            segment.plan_budget(
                refined,
                settings.EXTRACTION_SECTION_CHAR_BUDGET,
                settings.SEGMENT_TARGET_COUNT,
                settings.SEGMENT_MIN_BUDGET,
            ),
            settings.SEGMENT_MIN_CHARS,
        )
        if not segments:
            raise ValueError("조각이 하나도 만들어지지 않았습니다.")

        # 6. 조각 임베딩 ────────────────────────────────────────────
        vectors = await embed.embed_segments(segments)
        segment_rows = self.repo.add_segments(
            document_id=document.id, segments=segments, embeddings=vectors
        )

        # 5-b. 문장 앵커 (북마크·드래그·"33p 이 문장" 근거 표시용)
        # 8단계가 개념의 근거 문장 번호를 여기에 맞춰 돌려주므로 그대로 넘긴다.
        sentences_by_seq = sentences.split_all(segments)
        self.repo.add_sentences(
            sentences_by_seq=sentences_by_seq,
            segment_rows=segment_rows,
        )

        # 2-b. 그림을 조각과 본문 내 위치에 매단다 ───────────────────
        if figure_drafts:
            located = {
                element_id: (segment_rows[seq], offset)
                for element_id, (seq, offset) in figures.locate(
                    figure_drafts, segments, refined
                ).items()
                if seq in segment_rows
            }
            self.repo.add_figures(
                document_id=document.id,
                figures=figure_drafts,
                located=located,
            )
        self.db.commit()

        # 7. 목차 분류 ⭐ ────────────────────────────────────────────
        stage(DocStatus.TOPICS)
        assignment = await topics.classify(
            segments, settings.TOPIC_MAX_COUNT,
            toc=toc, page_sections=page_sections, body_sections=body_sections,
        )
        topic_rows = self.repo.add_topics(
            document_id=document.id,
            titles=[(t.seq, t.title) for t in assignment.topics],
        )

        topic_of_segment = {}
        for draft in assignment.topics:
            topic_row = topic_rows[draft.seq]
            members = []
            for seq in draft.segment_seqs:
                segment_row = segment_rows.get(seq)
                if segment_row is None:
                    continue
                self.repo.assign_topic(segment_row, topic_row)
                topic_of_segment[seq] = topic_row
                members.append(segment_row)
            self.repo.set_topic_pages(topic_row, members)
        self.db.commit()

        # 8~11. 개념 추출 → 임베딩 → 저장 ───────────────────────────
        stage(DocStatus.EXTRACTING)
        titles = {
            seq: topic.title for seq, topic in topic_of_segment.items()
        }
        extractions, failed = await concepts.extract_all(
            segments, titles, sentences_by_seq
        )

        # 9. 개념 임베딩 (저장 전에 배치로 한 번에)
        cache = await embed.embed_texts(persist.concept_texts(extractions))

        # 11. 저장 (2-pass)
        result = persist.persist(
            self.repo,
            document_id=document.id,
            extractions=extractions,
            segment_rows=segment_rows,
            topic_of_segment=topic_of_segment,
            embeddings=cache,
        )

        self.db.commit()

        # 10. 중복 정리 (임베딩 문턱 + LLM 판정, 원문 출처는 전부 이관)
        merge = await dedup.run(self.repo, document.id)
        self.db.commit()

        # 12. 밀도 판정 — "이 자료가 본문까지 될 수 있나"
        report = density.measure(
            segments,
            empty_segments=result.empty_segments,
            failed_segments=failed,
        )
        document.density_grade = report.grade
        document.avg_segment_chars = report.avg_chars
        document.chars_per_page = report.chars_per_page
        document.concept_coverage = report.coverage
        document.error = f"개념 추출 실패 조각: {failed}" if failed else None
        self.db.commit()

        stage(DocStatus.READY)
        _log.info(
            "파싱 완료: %s — 목차 %d · 조각 %d · 개념 %d(병합 %d) · %s(%s)",
            document.filename, len(assignment.topics), len(segments),
            result.concept_count - merge.total_merged, merge.total_merged,
            "본문 가능" if report.is_body else "뼈대만", report.reason,
        )

    # ── 조회 ──────────────────────────────────────────────────────

    # ── 검색 ──────────────────────────────────────────────────────

    async def search_concepts(
        self,
        query: str,
        *,
        limit: int = 10,
        document_ids: list[uuid.UUID] | None = None,
        min_sim: float = 0.0,
    ) -> list[ConceptHitOut]:
        """개념을 뜻으로 찾는다. 문서 경계를 넘는다.

        이름이 안 겹쳐도 찾는 게 요점이다 — 실측: "소프트웨어 비용 산정"으로
        검색하면 이름에 그 말이 없는 "COCOMO 모형"이 0.622로 올라온다.
        """
        vectors = await embed.embed_texts([query])
        vector = vectors.get(query)
        if vector is None:
            return []

        hits = self.repo.search_concepts(
            embedding=vector, limit=limit,
            document_ids=document_ids, min_sim=min_sim,
        )
        if not hits:
            return []

        # 근거 좌표는 문서마다 문장 표를 한 번씩만 읽어서 푼다.
        sentences_by_doc: dict[uuid.UUID, dict] = {}
        pages_by_doc: dict[uuid.UUID, dict] = {}
        results: list[ConceptHitOut] = []
        for concept, similarity in hits:
            doc_id = concept.document_id
            if doc_id not in sentences_by_doc:
                sentences_by_doc[doc_id] = self.repo.load_sentences(doc_id)
                pages_by_doc[doc_id] = {
                    s.seq: (s.page_from, s.page_to)
                    for s in self.repo.load_tree(doc_id)[1]
                }
            document = self.repo.get_document(doc_id)
            topic = self.db.get(DocTopic, concept.topic_id) if concept.topic_id else None
            results.append(
                ConceptHitOut(
                    id=concept.id,
                    name=concept.name,
                    definition=concept.definition,
                    source=concept.source,
                    global_key=concept.global_key,
                    similarity=round(similarity, 4),
                    document_id=doc_id,
                    filename=document.filename if document else "",
                    topic_title=topic.title if topic else None,
                    evidence=_evidence_of(
                        concept, sentences_by_doc[doc_id], pages_by_doc[doc_id]
                    ),
                )
            )
        return results

    def get_tree(self, document_id: uuid.UUID) -> DocumentTree:
        """목차 아래에 원문 조각과 개념이 다 들어 있는 구조를 돌려준다."""
        document = self.repo.get_document(document_id)
        if document is None:
            raise ValueError(f"문서를 찾을 수 없습니다: {document_id}")

        topic_rows, segment_rows, concept_rows, edge_rows = self.repo.load_tree(
            document_id
        )
        seq_of_segment = {s.id: s.seq for s in segment_rows}
        sentence_counts = self.repo.count_sentences(document_id)

        figures_by_segment: dict[uuid.UUID, list[FigureOut]] = {}
        for row in self.repo.list_figures(document_id):
            if row.segment_id is not None:
                figures_by_segment.setdefault(row.segment_id, []).append(
                    FigureOut.model_validate(row)
                )
        for items in figures_by_segment.values():
            items.sort(key=lambda f: f.char_offset)

        def to_segment(row) -> SegmentOut:
            return SegmentOut(
                id=row.id,
                seq=row.seq,
                heading=row.heading,
                content=row.content,
                page_from=row.page_from,
                page_to=row.page_to,
                char_count=row.char_count,
                sentence_count=sentence_counts.get(row.id, 0),
                figures=figures_by_segment.get(row.id, []),
            )

        prereqs: dict[uuid.UUID, list[uuid.UUID]] = {}
        for edge in edge_rows:
            if edge.kind == "prerequisite":
                prereqs.setdefault(edge.from_concept_id, []).append(edge.to_concept_id)

        segments_by_topic: dict[uuid.UUID | None, list] = {}
        for row in segment_rows:
            segments_by_topic.setdefault(row.topic_id, []).append(row)

        concepts_by_topic: dict[uuid.UUID | None, list] = {}
        for row in concept_rows:
            concepts_by_topic.setdefault(row.topic_id, []).append(row)

        sentences = self.repo.load_sentences(document_id)
        pages_of_segment = {s.seq: (s.page_from, s.page_to) for s in segment_rows}

        def to_concept(row) -> ConceptOut:
            return ConceptOut(
                id=row.id,
                name=row.name,
                definition=row.definition,
                source=row.source,
                global_key=row.global_key,
                segment_seqs=sorted(
                    seq_of_segment[link.segment_id]
                    for link in row.segment_links
                    if link.segment_id in seq_of_segment
                ),
                prerequisite_ids=prereqs.get(row.id, []),
                evidence=_evidence_of(row, sentences, pages_of_segment),
            )

        return DocumentTree(
            document=DocumentOut.model_validate(document),
            topics=[
                TopicOut(
                    id=topic.id,
                    seq=topic.seq,
                    title=topic.title,
                    page_from=topic.page_from,
                    page_to=topic.page_to,
                    segments=[
                        to_segment(s) for s in segments_by_topic.get(topic.id, [])
                    ],
                    concepts=[
                        to_concept(c) for c in concepts_by_topic.get(topic.id, [])
                    ],
                )
                for topic in topic_rows
            ],
            orphan_segments=[
                to_segment(s) for s in segments_by_topic.get(None, [])
            ],
        )


def _evidence_of(concept, sentences: dict, pages: dict) -> list[EvidenceOut]:
    """concepts.evidence_sentences([[조각 seq, 문장 seq], …])를 원문 좌표로 푼다.

    트리 조회와 검색이 같은 함수를 쓴다 — 두 군데서 따로 풀면 한쪽만 고쳐져
    같은 개념의 근거가 화면마다 다르게 보이게 된다.
    """
    out: list[EvidenceOut] = []
    for pair in concept.evidence_sentences or []:
        # JSONB를 거치며 형태가 흔들릴 수 있으니 방어적으로 읽는다.
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        sentence = sentences.get((pair[0], pair[1]))
        if sentence is None:
            continue
        page_from, page_to = pages.get(pair[0], (None, None))
        out.append(
            EvidenceOut(
                segment_seq=pair[0],
                sentence_seq=pair[1],
                char_start=sentence.char_start,
                char_end=sentence.char_end,
                text=sentence.text,
                page_from=page_from,
                page_to=page_to,
            )
        )
    return out
