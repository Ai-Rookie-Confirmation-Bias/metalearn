"""파싱 DocumentTree → 우리 Document.

seedParsec `GET /parsing/documents/{id}/tree` 응답(또는 같은 모양의 JSON)을
받아 목차→화면(슬라이스)으로 만든다. md 어댑터(`parsing_md`)와 역할이 같다 —
파싱 출력을 도메인에 직접 노출하지 않기 위한 층.

의미 묶음은 하지 않는다. 목차 안 개념을 원문·evidence 순으로 잘라 화면만 만든다.
"""
from __future__ import annotations

import re
from typing import Any

from ..grouping import Concept, Figure, Section, _figures_in, group_into_sections
from ..models import Chapter, Document


def _pages(topic: dict[str, Any]) -> str:
    lo, hi = topic.get("page_from"), topic.get("page_to")
    if lo is None and hi is None:
        return ""
    if lo is None:
        return f"p.{hi}"
    if hi is None or hi == lo:
        return f"p.{lo}"
    return f"p.{lo}-{hi}"


_JOIN = "\n\n"


def _joined_source(topic: dict[str, Any]) -> str:
    segs = sorted(topic.get("segments") or [], key=lambda s: int(s["seq"]))
    return _JOIN.join(s.get("content") or "" for s in segs)


def _segment_bases(topic: dict[str, Any]) -> dict[int, int]:
    """{조각 seq: `_joined_source` 안에서의 시작 위치}."""
    segs = sorted(topic.get("segments") or [], key=lambda s: int(s["seq"]))
    bases: dict[int, int] = {}
    base = 0
    for seg in segs:
        bases[int(seg["seq"])] = base
        base += len(seg.get("content") or "") + len(_JOIN)
    return bases


def _evidence_spans(
    keys: tuple[str, ...],
    by_name: dict[str, list[dict[str, Any]]],
    bases: dict[int, int],
) -> tuple[tuple[int, int], ...]:
    """화면 개념들의 **근거 문장 위치**를 joined 좌표로.

    ⚠️ 이게 왜 필요한가 — `split_by_concepts`(제목 매칭)는 코스 원문에서 자주
    실패한다. 개념명이 원문 제목과 안 맞기 때문이고, 그게 "교재 활용 41%"와
    같은 뿌리다. 실패하면 화면 좌표가 통째로 비어서 **그림을 한 장도 못 붙였다**
    (실측: 목차 하나에 그림 6장, 배정 0장).

    근거 문장은 개념마다 붙어 있으므로(부착률 99%) 여기서 위치를 얻는다.
    구간을 조금 넓혀 잡는다 — 그림은 보통 설명 문장 바로 앞뒤에 있다.
    """
    out: list[tuple[int, int]] = []
    for key in keys:
        for e in by_name.get(key) or []:
            base = bases.get(int(e.get("segment_seq", -1)))
            if base is None:
                continue
            lo = base + int(e.get("char_start", 0))
            hi = base + int(e.get("char_end", 0) or e.get("char_start", 0))
            out.append((max(0, lo - _FIGURE_REACH), hi + _FIGURE_REACH))
    return tuple(sorted(out))


# 근거 문장에서 이만큼 떨어진 그림까지 이 화면 후보로 본다. 조각 하나가
# 300~700자라 이 값이면 대략 같은 문단이다. **후보일 뿐** — 최종 배정은
# `_assign_figures`가 가장 가까운 화면 하나로 좁힌다.
_FIGURE_REACH = 400


def _assign_figures(
    figures: list[Figure],
    spans_per_screen: list[tuple[tuple[int, int], ...]],
) -> list[tuple[Figure, ...]]:
    """그림을 **한 화면에만** 준다.

    ⚠️ 구간이 겹치도록 넓혀 잡기 때문에(`_FIGURE_REACH`) 그냥 구간 검사만 하면
       같은 그림이 이웃 화면에 줄줄이 붙는다(실측: 한 다이어그램이 5화면 연속).
       같은 그림이 계속 나오면 학습자는 그걸 화면 장식으로 읽는다.

    거리는 구간까지의 최단 거리다. 구간 안이면 0이고, 그때는 먼저 오는(위쪽)
    화면이 가져간다 — 그림은 보통 자기를 설명하는 글보다 앞에 있다.
    """
    out: list[list[Figure]] = [[] for _ in spans_per_screen]
    for fig in figures:
        best: tuple[int, int] | None = None  # (거리, 화면 index)
        for i, spans in enumerate(spans_per_screen):
            for lo, hi in spans:
                d = 0 if lo <= fig.offset < hi else min(
                    abs(fig.offset - lo), abs(fig.offset - hi)
                )
                if best is None or d < best[0]:
                    best = (d, i)
        # 어느 화면 구간에도 닿지 않으면 버린다. 아무 데나 붙이면 관계없는
        # 그림이 설명 옆에 선다.
        if best is not None and best[0] <= _FIGURE_REACH:
            out[best[1]].append(fig)
    return [tuple(sorted(f, key=lambda x: x.offset)) for f in out]


def _joined_figures(topic: dict[str, Any]) -> list[Figure]:
    """이 목차의 그림들 — **`_joined_source`와 같은 좌표계로** 옮겨서.

    파싱은 `char_offset`을 **조각 안에서의 위치**로 준다. 우리는 목차의 조각을
    이어 붙여 한 덩어리로 쓰므로, 앞 조각들의 길이(+ 구분자)를 더해야 같은
    자를 쓰게 된다. 안 그러면 두 번째 조각의 그림이 전부 첫 화면에 몰린다.

    ⚠️ `_joined_source`와 **같은 구분자·같은 정렬**이어야 한다. 둘이 어긋나면
       조용히 어긋난 위치가 나온다(그림이 엉뚱한 화면에 붙는다).
    """
    segs = sorted(topic.get("segments") or [], key=lambda s: int(s["seq"]))
    out: list[Figure] = []
    base = 0
    for seg in segs:
        content = seg.get("content") or ""
        for f in seg.get("figures") or []:
            fid = f.get("id")
            if not fid:
                continue
            out.append(
                Figure(
                    figure_id=str(fid),
                    page=int(f.get("page") or 0),
                    offset=base + int(f.get("char_offset") or 0),
                    caption=(f.get("caption") or "").strip(),
                    needs_vision=bool(f.get("needs_vision")),
                )
            )
        base += len(content) + len(_JOIN)
    return out


def _evidence_order(concept: dict[str, Any]) -> int:
    """evidence가 있으면 (조각순, 문자offset), 없으면 큰 값 → 뒤로."""
    ev = concept.get("evidence") or []
    if not ev:
        return 10**9
    first = min(ev, key=lambda e: (int(e.get("segment_seq", 0)), int(e.get("char_start", 0))))
    return int(first.get("segment_seq", 0)) * 10**6 + int(first.get("char_start", 0))


def _source_from_evidence(
    keys: tuple[str, ...],
    by_name: dict[str, list[dict[str, Any]]],
) -> str:
    """화면 개념들의 evidence 문장을 이어 붙인다. **폴백 전용이다.**

    ⚠️ 이걸 1차 원문으로 쓰면 안 된다. 파싱 STATUS의 경고:

        근거 문장이 항상 정확하지는 않다. 3개 중 1~2개는 개념을 정확히 짚고
        나머지는 인접 문장을 함께 집는 수준이다. 위치를 짚어주는 용도로는 쓸 만하고,
        "이 문장만 딱 보여준다"에는 검증이 한 겹 더 필요하다.
        → 화면은 조각 본문을 통째로 받아 이 구간만 강조하라

    그래서 순서가 **조각 본문 우선, evidence는 폴백**이다. 이유 둘:
      · 📎 원문은 "AI가 지어낸 게 아니라 교재의 그 문장"이라는 근거다.
        틀린 문장을 보여주면 그 근거가 무너진다
      · evidence 몇 문장만 주면 설명 재료가 얇아진다.
        "설명이 원문을 다 못 담는다"가 이미 문제인데 더 나빠진다

    evidence의 **정확한** 용법은 `_evidence_order` 쪽이다 — 위치를 알려주는 것.
    """
    parts: list[str] = []
    seen: set[str] = set()
    for key in keys:
        for e in by_name.get(key) or []:
            text = (e.get("text") or "").strip()
            if text and text not in seen:
                seen.add(text)
                parts.append(text)
    return "\n\n".join(parts)


def document_from_tree(tree: dict[str, Any], *, doc_id: str | None = None) -> Document:
    """DocumentTree dict → 커리큘럼 Document.

    `doc_id`를 안 주면 document.filename 스템(없으면 id)을 쓴다.
    """
    meta = tree.get("document") or {}
    if doc_id is None:
        raw = meta.get("filename") or str(meta.get("id") or "document")
        doc_id = re.sub(r"\.[^.]+$", "", str(raw))
    title = str(meta.get("filename") or doc_id)

    # prerequisite_ids → 이름. 트리 전체에 대해 한 번 만든다.
    id_to_name: dict[str, str] = {}
    for topic in tree.get("topics") or []:
        for c in topic.get("concepts") or []:
            id_to_name[str(c["id"])] = c["name"]

    chapters: list[Chapter] = []
    topics = sorted(tree.get("topics") or [], key=lambda t: int(t.get("seq", 0)))
    for i, topic in enumerate(topics):
        joined = _joined_source(topic)
        pages = _pages(topic)
        by_name = {
            c["name"]: list(c.get("evidence") or []) for c in (topic.get("concepts") or [])
        }

        concepts: list[Concept] = []
        # 같은 이름이 두 번 오면 뒤에 것만 — 파싱이 중복을 안 지웠을 때의 방어.
        seen_names: set[str] = set()
        ranked = sorted(
            enumerate(topic.get("concepts") or []),
            key=lambda pair: (_evidence_order(pair[1]), pair[0]),
        )
        for list_i, c in ranked:
            name = c["name"]
            if name in seen_names:
                continue
            seen_names.add(name)
            prereqs = tuple(
                id_to_name[str(pid)]
                for pid in (c.get("prerequisite_ids") or [])
                if str(pid) in id_to_name and id_to_name[str(pid)] != name
            )
            concepts.append(
                Concept(
                    key=name,
                    definition=c.get("definition") or "",
                    prerequisites=prereqs,
                    order=_evidence_order(c) if c.get("evidence") else list_i,
                    chunk_id=str(topic.get("seq", i)),
                    # 파싱이 준 걸 버리지 않는다. 코스(다자료)가 붙으면 여기가
                    # 같은 개념을 합치는 근거가 된다 — `Concept.global_key` 참고.
                    global_key=str(c.get("global_key") or ""),
                )
            )

        all_figures = _joined_figures(topic)
        bases = _segment_bases(topic)
        screens = group_into_sections(concepts, joined, pages)
        picks = _assign_figures(
            all_figures,
            [_evidence_spans(s.concept_keys, by_name, bases) for s in screens],
        )
        enriched: list[Section] = []
        for j, s in enumerate(screens):
            # 조각 본문에서 개념 자리를 잘라낸 것이 1차. 개념을 하나라도 못 찾아
            # 비었을 때만 evidence로 메운다(위 `_source_from_evidence` 참고).
            enriched.append(
                Section(
                    title=s.title,
                    concepts=s.concepts,
                    reason=s.reason,
                    order=j,
                    source=s.source or _source_from_evidence(s.concept_keys, by_name),
                    page=s.page or pages,
                    section_id=s.section_id,
                    figures=picks[j],
                )
            )
        chapters.append(Chapter(index=i, title=topic.get("title") or f"목차 {i}", sections=tuple(enriched)))

    return Document(doc_id=doc_id, title=title, chapters=tuple(chapters))
