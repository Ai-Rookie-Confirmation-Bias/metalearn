"""커리큘럼 도메인 모델 — 어댑터·store가 같이 쓴다."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .grouping import Section


@dataclass(frozen=True)
class Chapter:
    """목차 하나 — 교재의 목차 그대로. 진단·학습 결과로 **바뀌지 않는다.**"""

    index: int
    title: str
    sections: tuple[Section, ...]

    @property
    def pages(self) -> str:
        """이 목차가 걸친 쪽 범위. 화면들의 쪽에서 최소~최대를 뽑는다."""
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
