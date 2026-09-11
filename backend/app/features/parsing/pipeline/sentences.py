"""5-b단계 — 문장 앵커. Solar 0회.

조각을 문장으로 쪼개고 각 문장에 순번과 위치(offset)를 붙인다.
**원문을 복사하지 않는다** — 조각 content 안의 구간을 가리키기만 하므로
조각이 원본이라는 불변식이 유지된다.

쓰이는 곳: 북마크 · 드래그 · "교재 33p 이 문장" 근거 표시.

한국어 문장 경계가 까다롭다:
  - 마침표만으로 못 자른다 ("1.5초", "Fig. 3", "예: A. B. C")
  - 표와 수식 내부는 절대 자르면 안 된다
  - 불릿 항목은 마침표가 없어도 한 문장이다
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

_log = logging.getLogger("uvicorn.error")

# 문장 끝: 종결부호 뒤에 공백/줄바꿈. 뒤에 닫는 따옴표·괄호가 붙을 수 있다.
_SENTENCE_END_RE = re.compile(r'(?<=[.!?。！？])["\')\]』」]*\s+')

# 마침표가 문장 끝이 아닌 경우 — 잘랐을 때 앞쪽이 이걸로 끝나면 되돌린다.
#   숫자 사이의 점(1.5), 한 글자 약어(Fig. / Dr. / No.), 번호 매기기(1. 2.)
_NOT_END_RE = re.compile(
    r"(\d\.|\b[A-Za-z]\.|\b(?:Fig|Dr|Mr|Ms|No|vs|etc|e\.g|i\.e)\.)$",
    re.IGNORECASE,
)

# 이 줄로 시작하면 표/코드 블록 — 통째로 한 덩어리로 둔다.
_ATOMIC_LINE_RE = re.compile(r"^\s*(\||```|\$\$|<table)")

# 불릿·번호 항목. 종결부호가 없어도 한 줄이 한 문장이다.
_BULLET_RE = re.compile(r"^\s*(?:[-*•·]|[①-⑳]|\(?\d+[.)]|[가-힣][.)])\s+")

# 너무 짧은 조각은 앞 문장에 붙인다. 한국어 문장은 짧다 —
# "표가 끝났다."가 7자다. 10자로 잡았더니 멀쩡한 문장이 앞 표에 흡수됐다.
_MIN_SENTENCE_CHARS = 4


@dataclass
class Sentence:
    seq: int
    text: str
    char_start: int
    char_end: int


def split(content: str) -> list[Sentence]:
    """조각 본문 → 문장 목록. char_start/end는 content 안의 offset이다."""
    if not content.strip():
        return []

    spans: list[tuple[int, int, bool]] = []  # (시작, 끝, 원자블록인가)
    for start, end in _line_blocks(content):
        block = content[start:end]
        if _ATOMIC_LINE_RE.match(block):
            spans.append((start, end, True))  # 표·수식은 안 쪼갠다
            continue
        spans.extend(
            (start + s, start + e, False) for s, e in _split_block(block)
        )

    sentences: list[Sentence] = []
    prev_atomic = False
    for start, end, atomic in spans:
        text = content[start:end].strip()
        if not text:
            continue
        # 너무 짧으면 앞 문장에 흡수. 단, 표·수식 덩어리에는 절대 붙이지
        # 않는다 — 붙이면 그 문장을 따로 가리킬 수 없게 된다.
        if sentences and not atomic and not prev_atomic and len(text) < _MIN_SENTENCE_CHARS:
            prev = sentences[-1]
            sentences[-1] = Sentence(
                seq=prev.seq,
                text=content[prev.char_start:end].strip(),
                char_start=prev.char_start,
                char_end=end,
            )
            continue
        sentences.append(
            Sentence(seq=len(sentences), text=text, char_start=start, char_end=end)
        )
        prev_atomic = atomic

    return sentences


def _line_blocks(content: str) -> list[tuple[int, int]]:
    """빈 줄과 표/코드 경계로 1차 분할. 반환은 (시작, 끝) offset."""
    blocks: list[tuple[int, int]] = []
    start = 0
    pos = 0
    atomic = False

    for line in content.splitlines(keepends=True):
        line_atomic = bool(_ATOMIC_LINE_RE.match(line))
        blank = not line.strip()
        # 원자 블록에 들어가거나 나올 때, 그리고 빈 줄에서 끊는다.
        if (line_atomic != atomic or blank) and pos > start:
            blocks.append((start, pos))
            start = pos
            atomic = line_atomic
        elif pos == start:
            atomic = line_atomic
        pos += len(line)

    if pos > start:
        blocks.append((start, pos))
    return blocks


def _split_block(block: str) -> list[tuple[int, int]]:
    """블록 하나를 문장 경계로 자른다. 반환은 블록 기준 offset."""
    spans: list[tuple[int, int]] = []
    for line_start, line_end in _bullet_lines(block):
        line = block[line_start:line_end]
        start = 0
        for match in _SENTENCE_END_RE.finditer(line):
            end = match.end()
            # 마침표가 문장 끝이 아니면(1.5초, Fig. 3) 자르지 않고 넘어간다.
            if _NOT_END_RE.search(line[start:match.start() + 1].rstrip()):
                continue
            spans.append((line_start + start, line_start + end))
            start = end
        if start < len(line):
            spans.append((line_start + start, line_end))
    return spans


def _bullet_lines(block: str) -> list[tuple[int, int]]:
    """불릿·번호 항목은 줄마다 끊는다.

    "- 최소값을 찾아 첫번째와 교환"처럼 종결부호가 없는 항목이 흔한데,
    안 끊으면 목록 전체가 문장 하나가 되어 앵커로 쓸 수 없다.
    """
    lines: list[tuple[int, int]] = []
    start = 0
    pos = 0
    for line in block.splitlines(keepends=True):
        if _BULLET_RE.match(line) and pos > start:
            lines.append((start, pos))
            start = pos
        pos += len(line)
    if pos > start:
        lines.append((start, pos))
    return lines or [(0, len(block))]


def split_all(segments) -> dict[int, list[Sentence]]:
    """{조각 seq: 문장 목록}. segments는 Segment 또는 DocSegment 모두 받는다."""
    result = {s.seq: split(s.content) for s in segments}
    total = sum(len(v) for v in result.values())
    _log.info("문장 분리: 조각 %d개 → 문장 %d개", len(result), total)
    return result
