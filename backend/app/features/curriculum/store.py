"""[인메모리 + 파일 스냅샷] 커리큘럼 저장소.

문서·화면은 서버가 뜰 때 픽스처에서 읽는다. 학습 기록은 메모리에 두되
`persist.py`가 JSON으로 남겨 **재시작해도 준비도가 0으로 안 돌아간다.**
(DB는 로드맵 — 붙으면 스냅샷 입출력만 바꾸면 된다.)

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
from dataclasses import dataclass, field, replace
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
from .planner import ChapterPlan, plan_course, supplement_sections

# 재export — router·벤치가 store에서 Document를 가져가던 경로 유지
__all__ = ["Chapter", "Document", "Progress", "Store", "build_document", "store", "summarize", "with_supplements"]

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

    def wrong_by_concept(self) -> dict[str, int]:
        """개념별 오답 횟수 — **화면을 넘나들며** 누적한다.

        보충 화면 삽입이 이걸 본다. 목차 단위 집계(`ChapterMastery.weak_concepts`)로는
        안 되는 이유: 선수 개념은 앞 목차에 있는 게 흔한데, 목차별로 끊어 세면
        1단원에서 틀린 게 3단원 보충의 근거가 되지 못한다.
        """
        out: dict[str, int] = {}
        for state in self.sections.values():
            for key, n in state.wrong_by_concept.items():
                out[key] = out.get(key, 0) + n
        return out


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


def _doc_id_from_tree(tree: dict, *, doc_id: str | None = None) -> str:
    """파싱 문서면 UUID를 키로 쓴다 — 책장→`/curriculum/{id}`가 그 id로 열려야 한다."""
    if doc_id:
        return doc_id
    meta = tree.get("document") or {}
    if meta.get("id"):
        return str(meta["id"])
    raw = meta.get("filename") or "document"
    return Path(str(raw)).stem


CARRY_LIMIT = 3


def with_supplements(doc: Document, progress: Progress) -> Document:
    """보충 화면이 끼워진 문서.

    **파싱이 준 문서는 안 건드린다.** 읽을 때마다 다시 계산한다 —
    `supplement_sections`가 순수 함수라 같은 상태면 같은 결과가 나오고,
    보충이 생기고 사라지는 시점이 오답 누적 하나로만 정해진다.

    개념 풀에 **문서 전체**를 넣는다. 선수는 앞 목차에 있는 경우가 흔해서
    목차 안에서만 찾으면 정작 필요한 걸 못 찾는다.
    """
    wrong = progress.wrong_by_concept()
    if not wrong:
        return doc
    pool = {c.key: c for ch in doc.chapters for s in ch.sections for c in s.concepts}
    return replace(
        doc,
        chapters=tuple(
            replace(ch, sections=tuple(supplement_sections(ch.sections, wrong, pool)))
            for ch in doc.chapters
        ),
    )


def summarize(doc: Document, progress: Progress) -> tuple[CourseMastery, list[ChapterPlan]]:
    """문서 전체 숙련도와 목차별 배분."""
    summaries: list[ChapterMastery] = [
        chapter_summary(
            ch.title,
            [progress.of(s.section_id) for s in ch.sections],
            # 보충 화면은 진도 분모에서 뺀다 — 끼울수록 진도가 뒤로 가면 안 된다.
            extra_ids=frozenset(s.section_id for s in ch.sections if s.inserted),
        )
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
        # 온보딩 전 — fixture_profile이 데모용 성향을 채운다.
        from .profile import fixture_profile

        self.profile = fixture_profile()

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

    def ingest_tree(self, tree: dict, *, doc_id: str | None = None) -> Document:
        """파싱 DocumentTree(dict)를 학습 store에 올린다.

        어댑터는 이미 있었다. 없던 건 **런타임 주입구**다 — 파일 픽스처만
        읽으면 머지 후 책장이 보여 주는 파싱 문서 id로 `/curriculum/{id}`가 404다.
        """
        key = _doc_id_from_tree(tree, doc_id=doc_id)
        doc = document_from_tree(tree, doc_id=key)
        self.documents[doc.doc_id] = doc
        return doc

    def ingest_course_tree(self, tree: dict, *, doc_id: str | None = None) -> Document:
        """코스 트리(dict)를 학습 store에 올린다. 키는 코스 id.

        문서와 같은 사전에 넣는다 — 화면 입장에서 "지금 보는 책 한 권"이라는
        점이 같고, 그래야 목차·학습·평가·채점이 코스에도 그대로 따라온다.
        """
        from .adapters.course_tree import document_from_course_tree

        doc = document_from_course_tree(tree, doc_id=doc_id)
        self.documents[doc.doc_id] = doc
        return doc

    def load_progress(self) -> int:
        """스냅샷에서 진도를 복원한다. 복원한 화면 수를 돌려준다."""
        from .persist import load_progress

        self.progress = load_progress()
        return len(self.progress.sections)

    def profile_block(self) -> str:
        from .profile import prompt_block

        return prompt_block(self.profile)

    def record(
        self,
        section_id: str,
        correct: bool,
        concept_key: str | None,
        kind: str = RETRIEVAL,
    ) -> SectionMastery:
        """시도 하나를 누적한다. **진단·인출·복습·형성이 전부 이 문을 지난다.**"""
        from .mastery import record
        from .persist import save_progress

        state = record(self.progress.of(section_id), correct, concept_key, kind)
        self.progress.sections[section_id] = state
        if not correct and concept_key:
            rw = self.progress.recent_wrong
            if concept_key in rw:
                rw.remove(concept_key)
            rw.append(concept_key)
            del rw[:-RECENT_WRONG]
        try:
            save_progress(self.progress)
        except OSError as e:
            # 디스크가 막혀도 이번 요청의 기록은 메모리에 남긴다.
            print(f"[curriculum] 진도 저장 실패: {type(e).__name__}: {e}")
        return state


store = Store()
