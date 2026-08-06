"""파싱 DocumentTree → quiz ParsedDocument.

`GET /api/parsing/documents/{id}/tree` 응답(또는 같은 모양의 JSON)을 받아
docs/QUIZ_INPUT.md 계약 형태로 바꾼다. 순수 변환 — LLM·DB 없음.

## 왜 필요했나

QUIZ_INPUT.md는 "파서 담당자용" 계약으로 쓰였고, 실제로 그 JSON을 만들어 주는
코드는 **아무 데도 없었다.** quiz는 소비만 하고 있었다. 통합 검증에서
파싱 산출물을 손으로 이 모양으로 옮겨 보니 **문항이 그대로 나왔다** —
없던 건 데이터가 아니라 배관이었다.

## 이름이 다른 것들 (계약 ↔ 파싱)

    chunks[]            ← topics[].segments[]
    chunks[].index      ← segments[].seq
    chunks[].raw_text   ← segments[].content
    chunks[].sentences  ← segments[].sentences   (offset만, text는 안 온다)
    chunks[].concepts   ← topics[].concepts 를 `segment_seqs`로 조각에 배분
    prereqs             ← prerequisite_ids 를 이름으로
    figures[].offset    ← figures[].char_offset
    tocs[]              ← topics[]

## 안 담는 것

`orphan_segments`는 chunks에 넣지 않는다. 목차에 배정되지 않은 조각이라
문항을 귀속시킬 데가 없다(quiz의 예산·범위 필터가 전부 목차 단위다).
파싱이 성공했다면 애초에 비어 있어야 한다 — 비어 있지 않으면 파싱 쪽 문제다.
"""
from __future__ import annotations

from typing import Any

from app.features.quiz.schemas import ParsedDocument


def _kind(category: str | None) -> str:
    return "chart" if "chart" in (category or "").lower() else "figure"


def _page(seg: dict[str, Any], topic: dict[str, Any], which: str) -> int:
    """페이지는 계약상 필수(int)인데 파싱은 None을 줄 수 있다.

    조각 → 목차 순으로 물려받고, 둘 다 없으면 0. 근거 표시가 "교재 N쪽"이라
    0이 나오면 화면에서 바로 보인다 — 조용히 빠지는 것보다 낫다.
    """
    for src in (seg, topic):
        v = src.get(which)
        if v is not None:
            return int(v)
    return 0


def parsed_from_tree(tree: dict[str, Any]) -> ParsedDocument:
    """DocumentTree dict → ParsedDocument."""
    meta = tree.get("document") or {}
    topics = sorted(tree.get("topics") or [], key=lambda t: int(t.get("seq", 0)))

    # prerequisite_ids → 이름. 트리 전체에 대해 한 번 만든다.
    id_to_name: dict[str, str] = {}
    for topic in topics:
        for c in topic.get("concepts") or []:
            id_to_name[str(c["id"])] = c["name"]

    chunks: list[dict[str, Any]] = []
    tocs: list[dict[str, Any]] = []

    for topic in topics:
        # 개념을 조각에 배분. 한 개념이 여러 조각에 걸치면 그 조각들 모두에 넣는다
        # — 중복 출제는 quiz planning이 multi_chunk 신호로 따로 다룬다.
        by_seq: dict[int, list[dict[str, Any]]] = {}
        for c in topic.get("concepts") or []:
            entry = {
                "name": c["name"],
                "definition": c.get("definition") or "",
                "prereqs": [
                    id_to_name[str(pid)]
                    for pid in (c.get("prerequisite_ids") or [])
                    if str(pid) in id_to_name and id_to_name[str(pid)] != c["name"]
                ],
            }
            for sq in c.get("segment_seqs") or []:
                by_seq.setdefault(int(sq), []).append(entry)

        segs = sorted(topic.get("segments") or [], key=lambda s: int(s["seq"]))
        for seg in segs:
            seq = int(seg["seq"])
            chunks.append({
                "index": seq,
                "page_from": _page(seg, topic, "page_from"),
                "page_to": _page(seg, topic, "page_to"),
                "raw_text": seg.get("content") or "",
                "sentences": [
                    {"start": int(s["char_start"]), "end": int(s["char_end"])}
                    for s in sorted(
                        seg.get("sentences") or [], key=lambda s: int(s.get("seq", 0))
                    )
                ],
                "concepts": by_seq.get(seq, []),
                "figures": [
                    {
                        "page": int(f.get("page") or 0),
                        "offset": int(f.get("char_offset") or 0),
                        "kind": _kind(f.get("category")),
                        "needs_vision": bool(f.get("needs_vision")),
                    }
                    for f in seg.get("figures") or []
                ],
            })

        tocs.append({
            "index": int(topic.get("seq", 0)),
            "title": topic.get("title") or f"목차 {topic.get('seq', 0)}",
            "chunk_indexes": [int(s["seq"]) for s in segs],
        })

    return ParsedDocument.model_validate({
        "parser_version": str(meta.get("parser_version") or "unknown"),
        "source_name": str(meta.get("filename") or ""),
        "tocs": tocs,
        "chunks": chunks,
    })
