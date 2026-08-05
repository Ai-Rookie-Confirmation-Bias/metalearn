"""[인메모리] 커리큘럼 저장소.

DB는 아직 없다(로드맵 STEP 3). 서버가 뜰 때 픽스처를 읽어 화면까지 만들어
메모리에 든다. **새로고침하면 학습 기록이 사라진다.**

층이 둘로 갈린다:

    공통  문서 → 목차 → 화면        문서당 한 번. 사용자 수와 무관
    개인  화면별 숙련도             사용자마다 다르다

입력은 두 갈래:
    *.tree.json  파싱 DocumentTree (정본 방향)
    *.md         예전 파싱 md 리포트 (레거시, 당분간 유지)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .adapters.parsing_tree import document_from_tree
from .grouping import Concept, Section, group_into_sections
from .mastery import (
    RETRIEVAL,
    ChapterMastery,
    CourseMastery,
    SectionMastery,
    chapter_summary,
    course_summary,
)
from .models import Chapter, Document
from .parsing_md import parse
from .planner import ChapterPlan, plan_course

# 재export — router·벤치가 store에서 Document를 가져가던 경로 유지
__all__ = ["Chapter", "Document", "Progress", "Store", "build_document", "store", "summarize"]

FIXTURE_DIR = Path(
    os.getenv("CURRICULUM_FIXTURES", Path(__file__).resolve().parents[3] / "tests/fixtures")
)

RECENT_WRONG = 8


@dataclass
class Progress:
    """한 사용자의 학습 상태. 화면 id → 숙련도."""

    sections: dict[str, SectionMastery] = field(default_factory=dict)
    recent_wrong: list[str] = field(default_factory=list)

    def of(self, section_id: str) -> SectionMastery:
        return self.sections.get(section_id) or SectionMastery(section_id=section_id)


def build_document(md_path: Path) -> Document:
    """파싱 md 하나 → 목차 → 화면(단순 슬라이스). 레거시 경로."""
    doc = parse(md_path)
    by_chapter: dict[str, list[Section]] = {}
    order: list[str] = []
    for chunk in doc.chunks:
        concepts = [
            Concept(c.key, c.definition, c.prerequisites, c.order, str(chunk.index))
            for c in chunk.concepts
        ]
        if chunk.chapter not in by_chapter:
            by_chapter[chunk.chapter] = []
            order.append(chunk.chapter)
        by_chapter[chunk.chapter] += group_into_sections(
            concepts, chunk.text, chunk.pages
        )

    chapters = []
    for i, title in enumerate(order):
        secs = tuple(
            Section(
                title=s.title,
                concepts=s.concepts,
                reason=s.reason,
                order=j,
                source=s.source,
                page=s.page,
                section_id=s.section_id,
            )
            for j, s in enumerate(by_chapter[title])
        )
        chapters.append(Chapter(index=i, title=title, sections=secs))
    return Document(doc_id=md_path.stem, title=doc.title, chapters=tuple(chapters))


def build_document_from_tree(path: Path) -> Document:
    """파싱 DocumentTree JSON → 목차 → 화면."""
    tree = json.loads(path.read_text(encoding="utf-8"))
    # foo.tree.json → doc_id=foo (파일명 우선, 트리 메타는 보조)
    stem = path.name.removesuffix(".tree.json") if path.name.endswith(".tree.json") else path.stem
    return document_from_tree(tree, doc_id=stem)


CARRY_LIMIT = 3


def summarize(doc: Document, progress: Progress) -> tuple[CourseMastery, list[ChapterPlan]]:
    """문서 전체 숙련도와 목차별 배분."""
    summaries: list[ChapterMastery] = [
        chapter_summary(ch.title, [progress.of(s.section_id) for s in ch.sections])
        for ch in doc.chapters
    ]

    carry: dict[str, tuple[str, ...]] = {}
    for prev, nxt in zip(summaries, summaries[1:]):
        if prev.weak_concepts:
            carry[nxt.chapter] = prev.weak_concepts[:CARRY_LIMIT]

    return course_summary(summaries), plan_course(summaries, carry)


class Store:
    """서버 하나가 들고 있는 전부. 사용자 구분은 아직 없다(단일 사용자 데모)."""

    def __init__(self) -> None:
        self.documents: dict[str, Document] = {}
        self.progress = Progress()

    def load_fixtures(self) -> list[str]:
        """tree.json을 먼저 읽고, 같은 stem의 md는 건너뛴다."""
        loaded_stems: set[str] = set()
        for path in sorted(FIXTURE_DIR.glob("*.tree.json")):
            doc = build_document_from_tree(path)
            self.documents[doc.doc_id] = doc
            loaded_stems.add(doc.doc_id)
        for path in sorted(FIXTURE_DIR.glob("*.md")):
            if path.stem in loaded_stems:
                continue
            doc = build_document(path)
            self.documents[doc.doc_id] = doc
        return list(self.documents)

    def record(
        self,
        section_id: str,
        correct: bool,
        concept_key: str | None,
        kind: str = RETRIEVAL,
    ) -> SectionMastery:
        """시도 하나를 누적한다. **진단·인출·복습·형성이 전부 이 문을 지난다.**"""
        from .mastery import record

        state = record(self.progress.of(section_id), correct, concept_key, kind)
        self.progress.sections[section_id] = state
        if not correct and concept_key:
            rw = self.progress.recent_wrong
            if concept_key in rw:
                rw.remove(concept_key)
            rw.append(concept_key)
            del rw[:-RECENT_WRONG]
        return state


store = Store()
