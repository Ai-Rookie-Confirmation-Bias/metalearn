"""문서 섹션 분할 (순수 로직, DB/LLM 비의존).

document-parse 결과를 LLM 추출 호출 단위(청크)로 나눈다
(ISSUE-008: 전체 문서 단일 호출 → 섹션별 호출로 커버리지 확보).

1순위 — 요소(elements) 기반 (`chunk_elements`):
  파서가 분류한 문단/표/수식/헤딩 요소 구조를 그대로 따른다.
  header/footer 노이즈를 제거하고, 요소를 절대 분할하지 않아
  수식·표의 원자성이 구조적으로 보장된다.

폴백 — 마크다운 헤딩 기반 (`split_sections` + `chunk_sections`):
  elements가 없을 때 마크다운을 헤딩 트리로 역추론해 분할.
- 인접 섹션은 문자 예산 안에서 병합해 호출 수를 줄인다.
  단, 최상위 헤딩(파트)이 바뀌면 병합하지 않는다 — 파트가 섞이면
  크로스 파트 선수관계 오류가 재발하기 때문.
- 예산을 넘는 단일 섹션은 문단 경계로 강제 분할한다.
- 헤딩이 전혀 없는 문서는 전체를 "(서문)" 섹션으로 보고 문단 분할로 폴백.
"""
import re
from dataclasses import dataclass
from typing import Any

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

# 이보다 짧은 청크는 개념이 나올 본문이 아니므로(목차 스텁, 파트 표지 등)
# LLM 호출 없이 버린다. 문서 전체가 이보다 짧은 극단 케이스만 예외로 유지.
_MIN_CHUNK_CHARS = 200

# 최상위 헤딩 종류가 이보다 많으면 '진짜 파트'가 아니라 플랫 헤딩 문서
# (document-parse가 모든 소제목을 #으로 뽑는 경우, 예: 정처기 노트의 "■ …").
# 이때는 파트 경계 병합 금지 규칙을 끈다 — 안 끄면 소제목마다 청크가 되어
# LLM 호출이 폭발(126청크 사례)하고 섹션 계층도 형성되지 않는다.
_MAX_REAL_PARTS = 12


@dataclass
class Section:
    path: list[str]  # 헤딩 경로 (최상위 → 자신)
    text: str        # 헤딩 줄 포함 원문


@dataclass
class Chunk:
    anchor: str  # 대표 헤딩 경로. 병합 청크는 "첫 경로 ~ 끝 제목", 분할은 "(part n)"
    text: str


# ── 요소(elements) 기반 청킹 — 1순위 경로 ───────────────────────────
# 페이지 장식 요소: 본문 개념과 무관한 노이즈라 청크에서 제외.
_SKIP_CATEGORIES = {"header", "footer", "footnote"}
_HEADING_CATEGORIES = {"heading1", "heading2", "heading3"}


def _element_text(element: dict[str, Any]) -> str:
    content = element.get("content") or {}
    return str(content.get("markdown") or content.get("text") or "").strip()


def chunk_elements(elements: list[dict[str, Any]], char_budget: int) -> list[Chunk]:
    """Document Parse 요소 배열을 청크로 병합한다.

    - header/footer/footnote 제외 (페이지 장식 노이즈 — 실측: 마크다운
      경로에선 전 청크 오염, 요소 경로에선 0)
    - heading* 요소가 섹션 경계, 문자 예산으로 인접 섹션 병합
    - 요소는 절대 분할하지 않음 → 수식($$...$$)·표 원자성 보장.
      예산을 넘는 단일 섹션은 통째로 한 청크가 된다.
    """
    sections: list[Section] = []
    cur_title: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf
        text = "\n\n".join(buf).strip()
        if text:
            sections.append(Section(path=[cur_title or "(서문)"], text=text))
        buf = []

    for element in elements:
        category = element.get("category")
        if category in _SKIP_CATEGORIES:
            continue
        text = _element_text(element)
        if not text:
            continue
        if category in _HEADING_CATEGORIES:
            flush()
            cur_title = text.lstrip("# ").strip()[:80]
        buf.append(text)
    flush()

    chunks: list[Chunk] = []
    group: list[Section] = []
    group_size = 0

    def close_group() -> None:
        nonlocal group, group_size
        if not group:
            return
        first, last = group[0].path[0], group[-1].path[0]
        anchor = first if first == last else f"{first} ~ {last}"
        chunks.append(Chunk(anchor=anchor, text="\n\n".join(s.text for s in group)))
        group, group_size = [], 0

    for sec in sections:
        if group and group_size + len(sec.text) > char_budget:
            close_group()
        group.append(sec)
        group_size += len(sec.text)
    close_group()

    substantial = [c for c in chunks if len(c.text) >= _MIN_CHUNK_CHARS]
    return substantial or chunks[:1]


def split_sections(raw_text: str) -> list[Section]:
    """헤딩마다 섹션을 끊고, 각 섹션에 헤딩 경로를 부여한다."""
    sections: list[Section] = []
    stack: list[tuple[int, str]] = []  # (level, title)
    cur_path: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf
        text = "\n".join(buf).strip()
        if text:
            sections.append(Section(path=list(cur_path) or ["(서문)"], text=text))
        buf = []

    for line in raw_text.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            flush()
            level = len(match.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, match.group(2)))
            cur_path = [title for _, title in stack]
        buf.append(line)
    flush()
    return sections


def chunk_sections(sections: list[Section], char_budget: int) -> list[Chunk]:
    """섹션들을 문자 예산 단위 청크로 병합/분할한다."""
    # 플랫 헤딩 문서 판정: 최상위 제목 종류가 많으면 헤딩이 파트가 아니라 소제목.
    flat = len({s.path[0] for s in sections}) > _MAX_REAL_PARTS

    chunks: list[Chunk] = []
    group: list[Section] = []
    group_size = 0

    def close_group() -> None:
        nonlocal group, group_size
        if not group:
            return
        first = " > ".join(group[0].path)
        anchor = first if len(group) == 1 else f"{first} ~ {group[-1].path[-1]}"
        chunks.append(Chunk(anchor=anchor, text="\n\n".join(s.text for s in group)))
        group, group_size = [], 0

    for sec in sections:
        if len(sec.text) > char_budget:
            close_group()
            parts = _split_by_paragraph(sec.text, char_budget)
            base = " > ".join(sec.path)
            for i, part in enumerate(parts, start=1):
                anchor = base if len(parts) == 1 else f"{base} (part {i})"
                chunks.append(Chunk(anchor=anchor, text=part))
            continue
        # 최상위 파트가 바뀌면 병합 금지 (크로스 파트 오염 방지).
        # 단, 플랫 헤딩 문서에선 규칙을 끈다 — 모든 소제목이 최상위라
        # 규칙이 병합 자체를 막아버리기 때문. 인접 소제목은 대개 같은 주제권.
        if group and (
            group_size + len(sec.text) > char_budget
            or (not flat and group[0].path[0] != sec.path[0])
        ):
            close_group()
        group.append(sec)
        group_size += len(sec.text)
    close_group()

    substantial = [c for c in chunks if len(c.text) >= _MIN_CHUNK_CHARS]
    return substantial or chunks[:1]


def _split_by_paragraph(text: str, char_budget: int) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    size = 0
    for para in text.split("\n\n"):
        if buf and size + len(para) > char_budget:
            parts.append("\n\n".join(buf))
            buf, size = [], 0
        buf.append(para)
        size += len(para) + 2
    if buf:
        parts.append("\n\n".join(buf))
    return parts
