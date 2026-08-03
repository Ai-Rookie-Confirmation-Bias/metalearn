"""[테스트 도구] 파싱 결과 md를 구조화 데이터로 읽는다.

실제 서비스는 DB에서 읽는다. 이 모듈은 **파싱 팀이 넘겨준 md를 테스트 케이스로
쓰기 위한 것**이다. 실제 규모(개념 533·634개)에서 절 묶기가 어떻게 되는지를
숫자로 보려면 손으로 옮긴 샘플로는 부족하다.

md 형식 (파서 v3.0):
    # 파싱 결과 — {파일}
    - 목차 N · 조각 N · 문장 N · 그림 N · 개념 N · 선후관계 N
    ## 목차                      ← 요약 표
    # 📂 {목차명}
    ## 📄 조각 #N
    `N자` · `p.A-B` · `요소 A~B` · 문장 N · 그림 N · 개념 N
    ### 이 조각에 걸린 개념 N개
    - **{이름}** — {정의}  · 선수: {A}, {B}
    ### 그림 N개
    - p.N · 본문 offset N · figure · {판정}
    ### 원문 (그대로)
    ```text
    ...
    ```
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_CHAPTER = re.compile(r"^# 📂 (.+)$")
_CHUNK = re.compile(r"^## 📄 조각 #(\d+)")
_CHUNK_META = re.compile(r"^`([\d,]+)자` · `p\.([\d\-]+)` · `요소 ([\d~]+)`")
_CONCEPT = re.compile(r"^- \*\*(.+?)\*\* — (.*?)(?:\s+· 선수: (.+))?$")
_FIGURE = re.compile(r"^- p\.(\d+) · 본문 offset (\d+) · (\S+) · (.+)$")
_H3 = re.compile(r"^### (.+)$")


@dataclass
class Figure:
    page: int
    offset: int
    kind: str
    note: str  # "비전 필요" | "주변 원문으로 충분"


@dataclass
class ParsedConcept:
    key: str
    definition: str
    prerequisites: tuple[str, ...]
    order: int  # 조각 안에서의 등장 순서(md 나열 순서)
    chunk_index: int
    chapter: str


@dataclass
class Chunk:
    index: int
    chars: int
    pages: str
    elements: str
    chapter: str
    concepts: list[ParsedConcept] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    text: str = ""


@dataclass
class ParsedDoc:
    title: str
    chunks: list[Chunk] = field(default_factory=list)

    @property
    def concepts(self) -> list[ParsedConcept]:
        return [c for ch in self.chunks for c in ch.concepts]

    def by_chapter(self) -> dict[str, list[Chunk]]:
        out: dict[str, list[Chunk]] = {}
        for ch in self.chunks:
            out.setdefault(ch.chapter, []).append(ch)
        return out


def parse(path: str | Path) -> ParsedDoc:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    doc = ParsedDoc(title=Path(path).stem)

    chapter = ""
    chunk: Chunk | None = None
    section = ""  # 현재 ### 소절: 개념 / 그림 / 원문
    in_code = False
    buf: list[str] = []
    order = 0

    def close() -> None:
        nonlocal chunk, buf
        if chunk is not None:
            chunk.text = "\n".join(buf).strip()
            doc.chunks.append(chunk)
        chunk, buf = None, []

    for raw in lines:
        line = raw.rstrip()

        # 원문 코드펜스 안은 그대로 담는다(들여쓰기·빈 줄 보존).
        if in_code:
            if line.startswith("```"):
                in_code = False
            else:
                buf.append(raw)
            continue

        if m := _CHAPTER.match(line):
            close()
            chapter = m.group(1).strip()
            continue

        if m := _CHUNK.match(line):
            close()
            chunk = Chunk(
                index=int(m.group(1)), chars=0, pages="", elements="", chapter=chapter
            )
            section = ""
            order = 0
            continue

        if chunk is None:
            continue

        if m := _CHUNK_META.match(line):
            chunk.chars = int(m.group(1).replace(",", ""))
            chunk.pages = m.group(2)
            chunk.elements = m.group(3)
            continue

        if m := _H3.match(line):
            head = m.group(1)
            section = (
                "concepts" if "개념" in head
                else "figures" if "그림" in head
                else "text" if "원문" in head
                else ""
            )
            continue

        if line.startswith("```"):
            in_code = section == "text"
            continue

        if section == "concepts" and (m := _CONCEPT.match(line)):
            pre = m.group(3) or ""
            chunk.concepts.append(
                ParsedConcept(
                    key=m.group(1).strip(),
                    definition=m.group(2).strip(),
                    prerequisites=tuple(
                        p.strip() for p in pre.split(",") if p.strip()
                    ),
                    order=order,
                    chunk_index=chunk.index,
                    chapter=chapter,
                )
            )
            order += 1
            continue

        if section == "figures" and (m := _FIGURE.match(line)):
            chunk.figures.append(
                Figure(
                    page=int(m.group(1)),
                    offset=int(m.group(2)),
                    kind=m.group(3),
                    note=m.group(4).strip(),
                )
            )

    close()
    return doc
