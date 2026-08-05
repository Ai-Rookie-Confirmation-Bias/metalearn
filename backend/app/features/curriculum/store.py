"""[인메모리] 커리큘럼 저장소.

DB는 아직 없다(로드맵 STEP 3). 지금은 서버가 뜰 때 파싱 md를 읽어 절까지 만들어
메모리에 들고 있는다. **새로고침하면 학습 기록이 사라진다** — 알고 하는 선택이고,
화면과 루프를 먼저 세우려는 것이다.

층이 둘로 갈린다:

    공통  문서 → 목차 → 절        문서당 한 번. 사용자 수와 무관하게 같다
    개인  절별 숙련도             사용자마다 다르다

절 묶기를 개인층에 두면 안 된다 — 나중에 ③(LLM 묶기)이 붙으면 사용자 수만큼 돈이
들고, 사람마다 절이 다르면 문제 페이지 쪽과 단위가 안 맞고 진도 비교도 못 한다.
교재 구조는 사람 따라 변하지 않는다. 변하는 건 그 위에서 무엇을 얼마나 보여주냐다.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .grouping import Concept, Section, group_into_sections
from .mastery import (
    RETRIEVAL,
    ChapterMastery,
    CourseMastery,
    SectionMastery,
    chapter_summary,
    course_summary,
)
from .parsing_md import parse
from .planner import ChapterPlan, plan_course

# 서버 시작 시 읽을 파싱 md. 파싱 팀과 통합하면 업로드로 바뀐다.
FIXTURE_DIR = Path(
    os.getenv("CURRICULUM_FIXTURES", Path(__file__).resolve().parents[3] / "tests/fixtures")
)


@dataclass(frozen=True)
class Chapter:
    """목차 하나 — 교재의 목차 그대로. 진단·학습 결과로 **바뀌지 않는다.**"""

    index: int
    title: str
    sections: tuple[Section, ...]

    @property
    def pages(self) -> str:
        """이 목차가 걸친 쪽 범위. 절들의 쪽에서 최소~최대를 뽑는다."""
        nums = [int(n) for s in self.sections for n in re.findall(r"\d+", s.page or "")]
        if not nums:
            return ""
        lo, hi = min(nums), max(nums)
        return f"p.{lo}" if lo == hi else f"p.{lo}-{hi}"


@dataclass(frozen=True)
class Document:
    """업로드한 자료 하나."""

    doc_id: str
    title: str
    chapters: tuple[Chapter, ...]

    def chapter(self, index: int) -> Chapter | None:
        return next((c for c in self.chapters if c.index == index), None)

    def section(self, section_id: str) -> tuple[Chapter, Section] | None:
        for ch in self.chapters:
            for s in ch.sections:
                if s.section_id == section_id:
                    return ch, s
        return None


# 최근 오답을 몇 개까지 들고 다니는가. 너무 길면 오래된 실수가 계속 따라온다.
RECENT_WRONG = 8


@dataclass
class Progress:
    """한 사용자의 학습 상태. 절 id → 숙련도."""

    sections: dict[str, SectionMastery] = field(default_factory=dict)
    # **방금 틀린 개념**. 절별 누적(`wrong_by_concept`)과 따로 둔다 —
    # 누적은 "이 사람의 약점"이고 이건 "바로 다음 절에서 짚을 것"이다.
    # 목차 단위로만 반영하면 목차 하나가 절 20개라 20절 뒤에 나타난다.
    recent_wrong: list[str] = field(default_factory=list)

    def of(self, section_id: str) -> SectionMastery:
        return self.sections.get(section_id) or SectionMastery(section_id=section_id)


def build_document(md_path: Path) -> Document:
    """파싱 md 하나 → 목차 → 절.

    조각을 순회하며 절을 만들고 목차로 모은다. 조각 경계는 여기서 사라진다.
    """
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
        # 조각을 넘나들며 모았으므로 목차 안에서 순서를 다시 매긴다.
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


# 다음 목차 설명에 녹일 약점 개념 상한. 많으면 설명이 산만해진다.
CARRY_LIMIT = 3


def summarize(doc: Document, progress: Progress) -> tuple[CourseMastery, list[ChapterPlan]]:
    """문서 전체 숙련도와 목차별 배분. **화면이 필요한 건 거의 다 여기서 나온다.**"""
    summaries: list[ChapterMastery] = [
        chapter_summary(ch.title, [progress.of(s.section_id) for s in ch.sections])
        for ch in doc.chapters
    ]

    # 앞 목차에서 약했던 개념을 **다음 목차 설명에 녹인다.**
    # 단원을 새로 만들지 않는 게 서비스 원칙이라, 넘길 곳은 다음 목차뿐이다.
    # 직전 목차 것만 넘긴다 — 전부 누적하면 뒤 목차가 앞의 빚을 다 떠안는다.
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
        for md in sorted(FIXTURE_DIR.glob("*.md")):
            doc = build_document(md)
            self.documents[doc.doc_id] = doc
        return list(self.documents)

    def record(
        self,
        section_id: str,
        correct: bool,
        concept_key: str | None,
        kind: str = RETRIEVAL,
    ) -> SectionMastery:
        """시도 하나를 누적한다. **진단·인출·복습·형성이 전부 이 문을 지난다.**

        지금 화면에서 오는 건 전부 인출이라 기본값을 그렇게 뒀다. 나머지 셋은
        붙일 때 `kind`만 넘기면 되고, 여기부터 아래는 손댈 게 없다.
        """
        from .mastery import record

        state = record(self.progress.of(section_id), correct, concept_key, kind)
        self.progress.sections[section_id] = state
        if not correct and concept_key:
            rw = self.progress.recent_wrong
            if concept_key in rw:
                rw.remove(concept_key)  # 다시 틀렸으면 맨 뒤로 — 더 최근이다
            rw.append(concept_key)
            del rw[:-RECENT_WRONG]
        return state


store = Store()
