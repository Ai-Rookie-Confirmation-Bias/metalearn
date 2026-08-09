"""[순수로직] 개념을 **화면 단위**로 자른다.

DB·LLM 비의존. 커리큘럼 엔진의 첫 단계이지만, **의미를 추론하지 않는다.**

## 왜 절 엔진을 버렸나

예전에는 ⓪표·①형제·①b사슬·②순환·③잡동사니로 "같이 배울 묶음"을
우리가 만들었다. 그 결과가 오묶음·잡동사니·슬러그 제목으로 설명·인출을
오염시켰다. 의미 묶음은 파싱/개념 그래프 몫이다.

## 지금 하는 일

조각·목차는 한 화면에 못 넣고, 개념 하나씩은 너무 잘다.
→ **원문 등장 순으로 N개씩** 잘라 화면을 만든다. 추론 없음.

파싱이 `lesson`을 주기 전까지의 임시 슬라이서다. lesson이 오면 그걸 그대로
쓰면 되고, 이 파일의 자르기 규칙은 빠진다.

타입 이름이 `Section`인 건 API·숙련도 키 호환 때문이다. 도메인 말은 **화면**.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from .excerpt import aliases, normalize_spaces, split_by_concepts

# 한 화면 목표 크기. 2~4 범위의 중앙. 마지막이 1개면 앞에 붙인다.
SCREEN_SIZE = 3


@dataclass(frozen=True)
class Concept:
    """파싱이 넘기는 개념 하나."""

    key: str  # 개념명. **화면에 보이는 이름이자 채점 대상 표기**다
    definition: str = ""
    prerequisites: tuple[str, ...] = ()
    order: int = 0  # 원문 등장 순서(파싱 md 나열. 원문 위치가 있으면 그걸로 재정렬)
    chunk_id: str | None = None
    # 문서 경계를 넘는 식별자(파싱 v3 `global_key`, 예: `cocomo-model`).
    # 지금은 들고만 다닌다 — 자료가 하나뿐이라 쓸 데가 없다.
    #
    # 코스(다자료)가 붙으면 여기가 필요해진다: PPT의 `모듈`과 교재의 `모듈`이
    # 이름은 같아도 파싱 상 다른 레코드라, 이름을 키로 쓰면 **같은 개념인데
    # 숙련도가 갈린다.** 반대로 이름이 다른 같은 개념(`XP`/`익스트림 프로그래밍`)도
    # 이게 있어야 합쳐진다.
    #
    # ⚠️ `key`를 global_key로 바꾸면 안 된다 — 화면 표시와 채점이 이름을 쓴다.
    #    식별자와 표기는 다른 일이다.
    global_key: str = ""


@dataclass(frozen=True)
class Figure:
    """원문에 실려 있던 그림 하나.

    **이미지 바이트는 안 들고 다닌다.** 파싱 DB에 있고 화면이 id로 받아 간다
    (`GET /api/parsing/documents/{doc}/figures/{id}`) — 자료 하나에 1.6MB짜리도
    있어서 트리·레슨 응답에 실으면 그것부터 느려진다.

    `offset`은 **조각 원문 기준** 문자 위치다. 어느 화면에 속하는지 가르는 데
    쓰고, 화면 안에서는 순서만 지킨다 — 설명은 우리가 새로 쓴 글이라 원문
    글자 위치에 정확히 끼울 자리가 없다.
    """

    figure_id: str
    page: int
    offset: int
    caption: str = ""
    # 파싱이 "텍스트만으로는 불완전하다"고 본 그림. 이게 참이면 설명이 그림을
    # 대신할 수 없다는 뜻이라, 화면이 더 크게 보여줄 근거가 된다.
    needs_vision: bool = False


@dataclass(frozen=True)
class Section:
    """화면 하나 = 한 번에 보여줄 개념 묶음 (단순 슬라이스)."""

    title: str
    concepts: tuple[Concept, ...]
    # 화면에 쓸 한 줄. 슬라이스라 속이 빈 ⚡ 구조를 만들지 않는다.
    reason: str
    order: int = 0
    source: str = ""  # 이 화면 개념들의 원문 구간(있으면)
    page: str = ""
    section_id: str = ""  # 진도 키. 내용이 바뀌면 새 화면으로 본다.
    # 이 화면이 어디서 왔는가. 빈 값이면 파싱이 준 원래 화면이다.
    #   "inserted"  반복해서 틀린 선수 개념을 위해 **우리가 끼운 보충 화면**
    #
    # ⚠️ **목차(단원)는 절대 안 만든다.** 파싱팀 `origin: inserted`(단원 삽입)를
    #    거절한 이유가 그것이다 — 목차 목록이 바뀌면 "목차는 고정" 원칙이 깨진다.
    #    화면은 다르다. 단원 1이 1.1~1.29에서 1.30이 되는 건 목차가 안 바뀐 것이다.
    #
    # ⚠️ 삽입 화면은 **진도 분모에서 뺀다**(`mastery.chapter_summary`). 안 그러면
    #    보충을 끼울수록 진도가 뒤로 가고 열려 있던 단원 평가가 다시 잠긴다 —
    #    학습을 했는데 벌을 받는 그림이다.
    origin: str = ""
    # 이 화면 원문 구간에 들어 있던 그림. 파싱이 위치까지 복원해 준 것을
    # 그대로 나른다 — 여기가 비면 화면은 텍스트만 남는다.
    figures: tuple[Figure, ...] = ()

    @property
    def inserted(self) -> bool:
        return self.origin == "inserted"

    @property
    def size(self) -> int:
        return len(self.concepts)

    @property
    def concept_keys(self) -> tuple[str, ...]:
        return tuple(c.key for c in self.concepts)


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", normalize_spaces(text))


def _positions(concepts: list[Concept], source: str) -> dict[str, int]:
    """원문에서 개념명이 처음 나오는 위치. 못 찾으면 빠진다."""
    body = _squash(source)
    out: dict[str, int] = {}
    for c in concepts:
        for name in aliases(c.key):
            i = body.find(_squash(name))
            if i >= 0:
                out[c.key] = i
                break
    return out


def _page_at(pages: str) -> str:
    """조각 쪽 범위 그대로. 추정하지 않는다."""
    if not pages:
        return ""
    return pages if pages.startswith("p.") else f"p.{pages}"


def _section_id(chunk_id: str | None, keys: tuple[str, ...]) -> str:
    raw = f"{chunk_id or ''}|{'|'.join(keys)}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def _batches(items: list[Concept], size: int) -> list[list[Concept]]:
    """size개씩 자른다. 마지막이 1개면 앞에 붙여 혼자인 화면을 없앤다."""
    if not items:
        return []
    out = [items[i : i + size] for i in range(0, len(items), size)]
    if len(out) > 1 and len(out[-1]) == 1:
        out[-2].extend(out.pop())
    return out


def _source_span(source: str, keys: tuple[str, ...]) -> tuple[str, tuple[tuple[int, int], ...]]:
    """화면 개념 구간의 **본문과 위치**. 일부라도 못 찾으면 비운다.

    예전에 section_source가 실패 시 조각 전체를 줬고, 그게 엉뚱한 원문 사고의
    원인이었다. 생성 쪽은 source가 비면 정의만으로 돌고, 📎도 안 뜬다.

    위치를 같이 돌려주는 이유: 그림이 **조각 원문 offset**으로 오는데, 어느
    화면 것인지 가르려면 화면이 원문의 어디인지 알아야 한다. 예전엔 텍스트만
    쓰고 좌표를 버려서 그림을 붙일 방법이 없었다.
    """
    if not source.strip():
        return "", ()
    excerpts = split_by_concepts(source, list(keys))
    if not excerpts or any(not e.matched for e in excerpts):
        return "", ()
    excerpts.sort(key=lambda e: e.start)
    spans = tuple((e.start, e.end) for e in excerpts)
    return "\n\n".join(e.text for e in excerpts), spans


def _figures_in(
    figures: list[Figure], spans: tuple[tuple[int, int], ...]
) -> tuple[Figure, ...]:
    """이 화면 구간에 들어오는 그림만, 원문 순서로."""
    if not figures or not spans:
        return ()
    hit = [f for f in figures if any(lo <= f.offset < hi for lo, hi in spans)]
    return tuple(sorted(hit, key=lambda f: f.offset))


def group_into_sections(
    concepts: list[Concept],
    source: str = "",
    pages: str = "",
    figures: list[Figure] | None = None,
) -> list[Section]:
    """개념 목록을 화면 단위로 자른다.

    원문이 있으면 등장 위치로 정렬하고, 없으면 `order`로 정렬한다.
    의미(선수·표·사슬)는 보지 않는다 — 파싱/그래프가 준 순서만 따른다.

    `figures`를 주면 각 화면의 원문 구간에 드는 것만 그 화면에 배정한다.
    구간 밖 그림은 버린다 — 아무 화면에나 붙이면 관계없는 그림이 설명 옆에
    선다.
    """
    if not concepts:
        return []

    if source.strip():
        pos = _positions(concepts, source)
        far = len(_squash(source)) + 1

        def sort_key(c: Concept) -> tuple[int, int, str]:
            return (pos.get(c.key, far), c.order, c.key)

    else:

        def sort_key(c: Concept) -> tuple[int, int, str]:
            return (c.order, 0, c.key)

    ordered = sorted(concepts, key=sort_key)
    chunk_id = next((c.chunk_id for c in ordered if c.chunk_id), None)
    page = _page_at(pages)

    out: list[Section] = []
    for i, batch in enumerate(_batches(ordered, SCREEN_SIZE)):
        keys = tuple(c.key for c in batch)
        text, spans = _source_span(source, keys)
        out.append(
            Section(
                title=batch[0].key,
                concepts=tuple(batch),
                # 슬라이스는 판단이 아니라 자르기라 ⚡에 올릴 이유가 없다.
                reason="",
                order=i,
                source=text,
                page=page,
                section_id=_section_id(chunk_id, keys),
                figures=_figures_in(figures or [], spans),
            )
        )
    return out
