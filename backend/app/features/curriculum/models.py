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
    # 이 목차가 어디서 왔는가. 빈 값이면 교재 목차 그대로.
    #   "inserted"  진단이 "모른다"고 한 과목을 채우려고 **코스 층이 끼운** 단원
    #
    # ⚠️ 화면에서 반드시 구분해 보여야 한다. 교재에 없는 내용인데 있는 것처럼
    #    보이면 "📎 원문은 AI가 지어낸 게 아니라 교재의 그 문장"이라는 우리
    #    근거가 통째로 흔들린다. 보강 단원은 조각이 없어 원문도 없다.
    #
    # ⚠️ `Section.inserted`와 다른 것이다 — 그건 우리가 화면 사이에 끼운 보충
    #    화면이고, 이건 진단이 목차 앞에 붙인 단원이다. 만든 주체도 층도 다르다.
    origin: str = ""

    @property
    def inserted(self) -> bool:
        return self.origin == "inserted"

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
    """업로드한 자료 하나(또는 수업 하나)."""

    doc_id: str
    title: str
    chapters: tuple[Chapter, ...]

    # ── 24 진단이 정한 것 ────────────────────────────────────────
    # 자료 하나짜리(파싱 문서)는 진단이 없어서 전부 비어 있다. 수업(코스)만
    # 채워져 온다.
    #
    # ⚠️ **이게 없으면 진단이 화면을 못 바꾼다.** 저장은 되는데 읽는 데가 없어서
    #    무엇을 고르든 설명과 분량이 같았다 — 바뀌는 건 보강 단원뿐이었다.
    #
    # metaphor | definition | table | why — 설명 형식
    style: str = ""
    # exam | work | interest — 분량의 방향
    goal: str = ""
    # 몇 주 남았나. 짧을수록 더 줄인다
    deadline_weeks: int | None = None

    def chapter(self, index: int) -> Chapter | None:
        return next((c for c in self.chapters if c.index == index), None)

    def section(self, section_id: str) -> tuple[Chapter, Section] | None:
        for ch in self.chapters:
            for s in ch.sections:
                if s.section_id == section_id:
                    return ch, s
        return None
