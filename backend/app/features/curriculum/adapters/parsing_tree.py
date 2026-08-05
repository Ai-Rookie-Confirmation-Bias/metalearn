"""파싱 DocumentTree → 우리 Document.

seedParsec `GET /parsing/documents/{id}/tree` 응답(또는 같은 모양의 JSON)을
받아 목차→화면(슬라이스)으로 만든다. md 어댑터(`parsing_md`)와 역할이 같다 —
파싱 출력을 도메인에 직접 노출하지 않기 위한 층.

의미 묶음은 하지 않는다. 목차 안 개념을 원문·evidence 순으로 잘라 화면만 만든다.
"""
from __future__ import annotations

import re
from typing import Any

from ..grouping import Concept, Section, group_into_sections
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


def _joined_source(topic: dict[str, Any]) -> str:
    segs = sorted(topic.get("segments") or [], key=lambda s: int(s["seq"]))
    return "\n\n".join(s.get("content") or "" for s in segs)


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

        screens = group_into_sections(concepts, joined, pages)
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
                )
            )
        chapters.append(Chapter(index=i, title=topic.get("title") or f"목차 {i}", sections=tuple(enriched)))

    return Document(doc_id=doc_id, title=title, chapters=tuple(chapters))
