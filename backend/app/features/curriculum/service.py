"""절 하나 → 학습 콘텐츠. **에이전트들을 잇는 자리.**

여기는 조립만 한다. 프롬프트는 각 에이전트가 갖는다 —
한 프롬프트에 "설명 만들어줘 + 문항 만들어줘"를 붙이지 않는다는 원칙 때문이다.

    explanation  절 → 설명 + 비유
        ↓ 설명 본문을 넘긴다 (이게 중요하다)
    retrieval    절 + 설명 → 빈칸 + 객관식

인출이 설명을 받아야 "읽게 하지 않고 꺼내게 한다"가 성립한다. 방금 읽은 글에서
꺼내는 것이지 아무 문항이나 붙이는 게 아니다.

## 왜 캐시하나

두 에이전트 합쳐 10~20초다. 화면을 열 때마다 부르면 못 쓴다. 그리고 **같은 절을
다시 열었을 때 다른 글이 나오면 안 된다** — 어제 본 설명이 오늘 바뀌면 학습자가
자기가 뭘 읽었는지 알 수 없다.

키에 성향을 넣는 이유: 성향이 바뀌면 설명 **형태**가 바뀌므로 다른 결과다.
내용 범위는 그대로다(성향은 표현만 바꾼다는 원칙).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from .agents import explanation as explain_agent
from .agents import retrieval as retrieval_agent
from .blocks import Block, ConceptBrief
from .grouping import Section

# 같은 절을 동시에 여러 번 열어도 한 번만 생성한다.
_locks: dict[str, asyncio.Lock] = {}


@dataclass(frozen=True)
class Lesson:
    """절 하나의 학습 콘텐츠 + 생성 품질 지표."""

    blocks: tuple[Block, ...]
    covered: int
    missing: tuple[str, ...]
    retrieval_gap: tuple[str, ...]
    # 인출 수준 분포(L1 재인 / L2 적용 / L3 구별). 화면엔 안 쓰고 품질 확인용.
    levels: dict[str, int] = field(default_factory=dict)
    retried: bool = False

    @property
    def ok(self) -> bool:
        """설명 본문이 나왔는가. 부가 항목은 없어도 화면은 선다."""
        return any(b.type == "concept" for b in self.blocks)


_cache: dict[str, Lesson] = {}


def _key(section: Section, profile_block: str) -> str:
    return f"{section.section_id}|{hash(profile_block)}"


async def build_lesson(
    section: Section, profile_block: str = "", *, refresh: bool = False
) -> Lesson:
    """절의 학습 콘텐츠를 만든다(캐시됨).

    생성이 실패하거나 응답이 깨져도 **예외를 올리지 않는다** — 블록이 빈 Lesson을
    돌려주고 화면이 "생성하지 못했습니다"를 보여주게 한다. 절 하나가 실패했다고
    목차 화면 전체가 죽으면 손해가 크다.
    """
    key = _key(section, profile_block)
    if not refresh and key in _cache:
        return _cache[key]

    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        if not refresh and key in _cache:  # 기다리는 동안 다른 요청이 채웠을 수 있다
            return _cache[key]

        briefs = [ConceptBrief(c.key, c.definition) for c in section.concepts]

        exp = await explain_agent.generate(
            section.title, briefs, profile_block, section.source
        )
        if not exp.ok:
            return Lesson(blocks=(), covered=0, missing=(), retrieval_gap=())

        ret = await retrieval_agent.generate(
            section.title, briefs, exp.text, section.source
        )

        lesson = Lesson(
            blocks=exp.blocks + ret.blocks,
            covered=exp.covered,
            missing=exp.missing,
            retrieval_gap=ret.gap,
            levels=ret.levels,
            retried=ret.retried,
        )
        if lesson.ok:  # 실패한 생성을 캐시에 남기면 계속 실패한 걸 보게 된다
            _cache[key] = lesson
        return lesson
