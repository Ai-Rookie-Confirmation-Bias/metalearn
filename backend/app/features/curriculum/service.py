"""절 하나 → 학습 블록. LLM을 부르는 유일한 자리.

`blocks.py`는 프롬프트를 만들고 응답을 검증하는 순수 로직이고, 호출은 여기서 한다.

## 왜 캐시하나

한 절 생성이 5~7초다. 화면을 열 때마다 부르면 못 쓴다. 그리고 **같은 절을 다시
열었을 때 다른 글이 나오면 안 된다** — 어제 본 설명이 오늘 바뀌면 학습자가
자기가 뭘 읽었는지 알 수 없다.

키에 성향을 넣는 이유: 성향이 바뀌면 설명 **형태**가 바뀌어야 하므로 다른 결과다.
내용 범위는 그대로다(성향은 표현만 바꾼다는 원칙).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.core.llm.solar import solar_client

from .blocks import (
    Block,
    ConceptBrief,
    build_prompt,
    coverage,
    parse_response,
    retrieval_gap,
)
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
    """절의 학습 블록을 만든다(캐시됨).

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
        prompt = build_prompt(section.title, briefs, profile_block, section.source)
        try:
            raw = await solar_client.generate(
                prompt,
                response_format={"type": "json_object"},
                temperature=0.3,
            )
        except Exception as e:  # noqa: BLE001
            print(f"[curriculum] 생성 실패 {section.title}: {type(e).__name__}: {e}")
            return Lesson(blocks=(), covered=0, missing=(), retrieval_gap=())

        blocks = parse_response(raw, briefs, section.source)
        covered, missing = coverage(blocks, briefs)
        lesson = Lesson(
            blocks=tuple(blocks),
            covered=covered,
            missing=tuple(missing),
            retrieval_gap=tuple(retrieval_gap(blocks, briefs)),
        )
        if lesson.ok:  # 실패한 생성을 캐시에 남기면 계속 실패한 걸 보게 된다
            _cache[key] = lesson
        return lesson
