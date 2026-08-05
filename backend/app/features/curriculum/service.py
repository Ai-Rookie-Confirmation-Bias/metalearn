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
from .agents import formative as formative_agent
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
    # 이 설명이 **실제로 엮은** 약점 개념. 화면 ⚡의 근거이자, 비어 있으면
    # ⚡를 안 띄우는 근거이기도 하다.
    tied_in: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """설명 본문이 나왔는가. 부가 항목은 없어도 화면은 선다."""
        return any(b.type == "concept" for b in self.blocks)


_cache: dict[str, Lesson] = {}


def _key(section: Section, profile_block: str, weak: tuple[str, ...]) -> str:
    """캐시 키.

    약점을 키에 넣는 이유: 안 넣으면 처음 연 절이 계속 나온다. 문항을 틀리고
    다시 열었는데 어제와 똑같은 글이면 "AI가 나를 보고 바꿨다"가 거짓이 된다.
    반대로 약점이 그대로면 같은 글이 나와야 한다 — 열 때마다 바뀌어도 안 된다.
    """
    return f"{section.section_id}|{hash(profile_block)}|{hash(weak)}"


_review_cache: dict[str, tuple[Block, ...]] = {}


async def build_review(section: Section, seed: int) -> tuple[Block, ...]:
    """복습 문항 — **설명 없이 문항만.**

    복습은 잊혀가는 걸 되살리는 자리다. 설명을 다시 보여주면 그건 복습이 아니라
    재인이고, "읽었으니 안다"는 착각만 늘린다(인출 에이전트가 L1을 강등시키는
    이유와 같다).

    **문항을 새로 만든다.** 그때 그 빈칸을 다시 내면 개념이 아니라 **그 문장을
    외웠는지**를 재게 된다. 망각곡선이 재는 건 개념 쪽이다.

    seed: 그 화면의 시도 횟수. 답을 내기 전까지는 같은 문항을 보여준다 —
    새로고침할 때마다 문항이 바뀌면 풀던 걸 잃는다. 답하면 seed가 올라
    다음 복습에는 새 문항이 나온다.
    """
    key = f"{section.section_id}|{seed}"
    if key in _review_cache:
        return _review_cache[key]

    lock = _locks.setdefault(f"r:{key}", asyncio.Lock())
    async with lock:
        if key in _review_cache:
            return _review_cache[key]
        briefs = [ConceptBrief(c.key, c.definition) for c in section.concepts]
        # 원문이 근거다. 설명을 만들지 않으니 설명 콜이 없다(복습은 화면당 1콜).
        grounds = section.source or "\n\n".join(c.definition for c in briefs)
        blocks = tuple(
            b
            for b in await retrieval_agent.fill_only(section.title, briefs, grounds)
            if b.type == "cloze"
        )
        if blocks:
            _review_cache[key] = blocks
        return blocks


async def _tie_in_cloze(section: Section, exp) -> Block | None:
    """다시 설명에 붙일 빈칸 하나. 조건이 안 맞으면 None(콜을 안 쓴다)."""
    tie = next((b for b in exp.blocks if b.type == "tie_in"), None)
    if tie is None or not tie.content.get("more") or not exp.tied_in:
        return None
    key = exp.tied_in[0]
    # 정의는 이 화면에 없다(지난 개념이다). 다시 설명 본문이 곧 근거다.
    return await retrieval_agent.recall_one(
        section.title, ConceptBrief(key, ""), str(tie.content["more"])
    )


def _with_tie_in_cloze(blocks: tuple[Block, ...], cloze: Block | None) -> tuple[Block, ...]:
    """빈칸을 tie_in 블록 **안에** 넣는다.

    별도 블록으로 뒤에 붙이면 접힘 밖에 남아, 안 펼친 사람에게 맥락 없는 빈칸이
    먼저 보인다. 화면이 순서를 다시 판단하지 않도록 여기서 담아 보낸다.
    """
    if cloze is None:
        return blocks
    return tuple(
        Block(b.type, {**b.content, "cloze": dict(cloze.content)}, b.concept_keys)
        if b.type == "tie_in"
        else b
        for b in blocks
    )


async def build_lesson(
    section: Section,
    profile_block: str = "",
    weak_concepts: tuple[str, ...] = (),
    *,
    foreign_keys: tuple[str, ...] = (),
    refresh: bool = False,
) -> Lesson:
    """절의 학습 콘텐츠를 만든다(캐시됨).

    weak_concepts: 이 학습자가 최근 틀린 개념 중 **이 절과 이어지는 것**만.
    고르는 일은 `planner.weak_for_section`이 한다 — 여기는 조립만 하는 자리다.

    foreign_keys: 문서 전체 개념 중 이 화면에 없는 것. 인출 라벨 검증이
    "다른 화면 개념이 정답"인 문항을 버릴 때 쓴다.

    생성이 실패하거나 응답이 깨져도 **예외를 올리지 않는다** — 블록이 빈 Lesson을
    돌려주고 화면이 "생성하지 못했습니다"를 보여주게 한다. 절 하나가 실패했다고
    목차 화면 전체가 죽으면 손해가 크다.
    """
    key = _key(section, profile_block, weak_concepts)
    if not refresh and key in _cache:
        return _cache[key]

    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        if not refresh and key in _cache:  # 기다리는 동안 다른 요청이 채웠을 수 있다
            return _cache[key]

        briefs = [ConceptBrief(c.key, c.definition) for c in section.concepts]

        exp = await explain_agent.generate(
            section.title, briefs, profile_block, section.source, weak_concepts
        )
        if not exp.ok:
            return Lesson(blocks=(), covered=0, missing=(), retrieval_gap=())

        ret = await retrieval_agent.generate(
            section.title,
            briefs,
            exp.text,
            section.source,
            foreign_keys=foreign_keys,
        )

        # 다시 설명을 펼친 자리에 붙일 빈칸. **tie_in이 실제로 엮였을 때만** 부른다
        # (`exp.tied_in`은 문단과 개념명이 둘 다 있어야 채워진다). 요청만 하고
        # 안 엮인 화면에서까지 콜을 쓰면 안 쓸 문항에 돈을 쓰는 것이다.
        blocks = _with_tie_in_cloze(
            exp.blocks,
            await _tie_in_cloze(section, exp),
        )

        lesson = Lesson(
            blocks=blocks + ret.blocks,
            covered=exp.covered,
            missing=exp.missing,
            retrieval_gap=ret.gap,
            levels=ret.levels,
            retried=ret.retried,
            tied_in=exp.tied_in,
        )
        if lesson.ok:  # 실패한 생성을 캐시에 남기면 계속 실패한 걸 보게 된다
            _cache[key] = lesson
        return lesson


# ── 형성평가 ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Formative:
    """목차 하나의 형성평가 + 품질 지표."""

    blocks: tuple[Block, ...]
    # 화면을 가로지른 문항 수. 이게 낮으면 인출 몰아보기와 다르지 않다
    crossing: int = 0
    # 이 평가가 실제로 확인하는 약점 개념. 요청이 아니라 들어간 것
    covered_weak: tuple[str, ...] = ()
    levels: dict[str, int] = field(default_factory=dict)
    retried: bool = False

    @property
    def ok(self) -> bool:
        return bool(self.blocks)


_formative_cache: dict[str, Formative] = {}


def _formative_key(chapter_title: str, weak: tuple[str, ...]) -> str:
    """약점이 바뀌면 다시 만든다 — 형성평가는 **지금의 약점**을 확인하는 자리다.

    진도(어느 화면을 봤는지)는 키에 안 넣는다. 넣으면 화면 하나 볼 때마다 평가가
    새로 만들어져, 열어놓고 푸는 도중에 문항이 바뀐다.
    """
    return f"{chapter_title}|{hash(weak)}"


async def build_formative(
    chapter_title: str,
    screens: list[tuple[str, tuple[ConceptBrief, ...], int]],
    weak: tuple[str, ...] = (),
    *,
    refresh: bool = False,
) -> Formative:
    """목차 하나의 형성평가(캐시됨).

    screens: (화면 제목, 개념들, 그 화면의 시도 횟수) — 시도 횟수가 있어야
    **아직 안 풀어본 화면**을 우선해서 물을 수 있다(미측정 자리 메우기).
    """
    key = _formative_key(chapter_title, weak)
    if not refresh and key in _formative_cache:
        return _formative_cache[key]

    lock = _locks.setdefault(f"f:{key}", asyncio.Lock())
    async with lock:
        if not refresh and key in _formative_cache:
            return _formative_cache[key]

        res = await formative_agent.generate(chapter_title, screens, weak)
        out = Formative(
            blocks=res.blocks,
            crossing=res.crossing,
            covered_weak=res.covered_weak,
            levels=res.levels,
            retried=res.retried,
        )
        if out.ok:
            _formative_cache[key] = out
        return out
