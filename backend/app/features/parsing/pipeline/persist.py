"""11단계 — 개념 그래프 저장. Solar 0회 (임베딩은 호출측에서 미리 받아둔다).

**2-pass 구조를 유지한다.**

  1바퀴: 모든 조각의 본문 개념을 먼저 등록 → source=book 확정
  2바퀴: 그 다음에야 선수관계 연결 → 새로 생기는 것만 ai_prereq

왜 2-pass인가 — 개념 X가 조각 A에서는 본문 타겟이고 조각 B에서는 선수개념일
수 있다. 순서가 섞이면 X가 "교재 밖 보충 지식"으로 잘못 낙인찍힌다.

기존 대비 고친 것 — **출처를 단수 FK가 아니라 다대다로 쌓는다.**
개념이 6p·11p·15p에 나오면 링크 3개가 남는다. 기존은 첫 등장만 저장했다.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from app.features.parsing.models import Concept, DocSegment, DocTopic
from app.features.parsing.pipeline.naming import is_usable_concept, normalize_name
from app.features.parsing.repository import ParsingRepository
from app.features.parsing.schemas import ConceptNode, ExtractionResult

_log = logging.getLogger("uvicorn.error")


@dataclass
class PersistResult:
    concept_count: int = 0
    edge_count: int = 0
    link_count: int = 0
    # 개념이 하나도 붙지 않은 조각 seq. 12단계 커버리지 계산에 쓴다.
    empty_segments: list[int] = field(default_factory=list)
    # 이름 필터에 걸려 버린 것 (기호·구조 단어). 프롬프트가 새는지 보는 지표.
    rejected: list[str] = field(default_factory=list)
    # 순환을 만들어서 버린 선후관계 간선 수.
    cycles_dropped: int = 0


def concept_texts(extractions: dict[int, ExtractionResult]) -> list[str]:
    """임베딩할 텍스트 목록. 저장 순회와 같은 순서로 모은다.

    호출측이 이걸로 배치 임베딩을 받아 persist에 캐시로 넘긴다.
    """
    texts: list[str] = []
    seen: set[str] = set()

    def collect(node: ConceptNode) -> None:
        norm = normalize_name(node.name)
        if norm not in seen:
            seen.add(norm)
            texts.append(_embed_key(node))
        for child in node.prerequisites:
            collect(child)

    # 본문 개념 먼저, 선수개념은 그 뒤 — 저장 순회와 같은 순서.
    for seq in sorted(extractions):
        for root in extractions[seq].concepts:
            norm = normalize_name(root.name)
            if norm not in seen:
                seen.add(norm)
                texts.append(_embed_key(root))
    for seq in sorted(extractions):
        for root in extractions[seq].concepts:
            collect(root)

    return texts


def _embed_key(node: ConceptNode) -> str:
    return f"{node.name}\n{node.description}"


def persist(
    repo: ParsingRepository,
    *,
    document_id: uuid.UUID,
    extractions: dict[int, ExtractionResult],
    segment_rows: dict[int, DocSegment],
    topic_of_segment: dict[int, DocTopic],
    embeddings: dict[str, list[float]],
) -> PersistResult:
    """추출 결과를 개념 그래프로 저장한다."""
    by_norm: dict[str, Concept] = {}
    edges: set[tuple[uuid.UUID, uuid.UUID, str]] = set()
    result = PersistResult()

    def evidence_of(node: ConceptNode, segment: DocSegment | None) -> list[list[int]]:
        """근거를 [조각 seq, 문장 seq] 쌍으로 만든다.

        조각 번호를 함께 남기는 이유: 개념 하나가 조각 여러 개에 걸치는데
        문장 번호는 조각 안에서만 유효하다. 번호만 쌓으면 나중에 어느 조각의
        몇 번째 문장인지 복원할 수 없다.
        """
        if segment is None or not node.evidence:
            return []
        return [[segment.seq, i] for i in node.evidence]

    def resolve(
        node: ConceptNode, *, source: str, segment: DocSegment | None
    ) -> Concept | None:
        """개념을 찾거나 만든다. 이름 정규화로 1차 합침 (임베딩 병합은 M2)."""
        if not is_usable_concept(node.name):
            result.rejected.append(node.name)
            return None
        norm = normalize_name(node.name)
        concept = by_norm.get(norm)
        evidence = evidence_of(node, segment)

        if concept is not None and evidence:
            # 같은 개념을 다른 조각에서 또 만나면 근거를 **더한다.** 덮어쓰면
            # 다대다로 쌓은 원문 주소와 근거가 어긋난다.
            merged = list(concept.evidence_sentences or [])
            for pair in evidence:
                if pair not in merged:
                    merged.append(pair)
            concept.evidence_sentences = merged

        if concept is None:
            topic = topic_of_segment.get(segment.seq) if segment is not None else None
            concept = repo.add_concept(
                document_id=document_id,
                topic_id=topic.id if topic is not None else None,
                name=node.name,
                normalized_name=norm,
                definition=node.description,
                global_key=_sanitize_slug(node.key),
                source=source,
                embedding=embeddings.get(_embed_key(node)),
                evidence_sentences=evidence,
            )
            by_norm[norm] = concept
            result.concept_count += 1
        elif source == "book" and concept.source == "ai_prereq":
            # 교재에 실제로 설명이 있는 쪽이 권위다.
            concept.source = "book"
            concept.definition = node.description
            if segment is not None and concept.topic_id is None:
                topic = topic_of_segment.get(segment.seq)
                concept.topic_id = topic.id if topic is not None else None

        # 2-pass라 같은 (개념, 조각) 쌍을 두 번 만난다. 새로 만든 것만 센다.
        if segment is not None and repo.link_concept_segment(
            concept_id=concept.id, segment_id=segment.id
        ):
            result.link_count += 1
        return concept

    # ── 1바퀴: 본문 개념 전부 먼저 (source=book 확정) ─────────────
    for seq in sorted(extractions):
        segment = segment_rows.get(seq)
        if segment is None:
            continue
        roots = extractions[seq].concepts
        if not roots:
            result.empty_segments.append(seq)
        for root in roots:
            resolve(root, source="book", segment=segment)

    # ── 2바퀴: 선수관계 연결 ───────────────────────────────────────
    # 선수관계 인접 목록. 순환을 막는 데만 쓴다.
    prereq_of: dict[uuid.UUID, set[uuid.UUID]] = {}

    def would_cycle(parent: uuid.UUID, child: uuid.UUID) -> bool:
        """child에서 parent로 이미 갈 수 있으면 이 간선은 뺑뺑이를 만든다.

        실측: ryan에서 "A를 알아야 B, B를 알아야 A" 간선이 4개 나왔다.
        LLM이 조각마다 따로 판단하니 문서 전체로 보면 앞뒤가 뒤집힌다.
        순환이 있으면 진단의 walk-down이나 커리큘럼 순서 정렬이 무한루프에
        빠지므로, **나중에 온 간선을 버린다** — 먼저 본 판단을 신뢰한다.
        """
        stack = [child]
        seen: set[uuid.UUID] = set()
        while stack:
            node_id = stack.pop()
            if node_id == parent:
                return True
            if node_id in seen:
                continue
            seen.add(node_id)
            stack.extend(prereq_of.get(node_id, ()))
        return False

    def connect(node: ConceptNode, segment: DocSegment | None) -> Concept | None:
        concept = resolve(
            node,
            source="book" if segment is not None else "ai_prereq",
            segment=segment,
        )
        if concept is None:
            return None
        for child_node in node.prerequisites:
            child = connect(child_node, None)
            if child is None:
                continue
            edge = (concept.id, child.id, "prerequisite")
            if child.id != concept.id and would_cycle(concept.id, child.id):
                result.cycles_dropped += 1
                _log.debug("순환 간선 버림: %r → %r", concept.name, child.name)
                continue
            if child.id != concept.id and edge not in edges:
                prereq_of.setdefault(concept.id, set()).add(child.id)
                repo.add_edge(
                    document_id=document_id,
                    from_concept_id=concept.id,
                    to_concept_id=child.id,
                )
                edges.add(edge)
                result.edge_count += 1
        return concept

    for seq in sorted(extractions):
        segment = segment_rows.get(seq)
        if segment is None:
            continue
        for root in extractions[seq].concepts:
            connect(root, segment)

    _log.info(
        "그래프 저장: 개념 %d개 · 선후관계 %d개 · 원문 링크 %d개 "
        "(개념 없는 조각 %d개, 이름 필터로 버림 %d개, 순환 간선 버림 %d개)",
        result.concept_count, result.edge_count, result.link_count,
        len(result.empty_segments), len(result.rejected), result.cycles_dropped,
    )
    return result


_SLUG_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789-")


def _sanitize_slug(raw: str | None) -> str | None:
    """형식 위반 슬러그는 버린다 — 13단계 전역 키 부여가 폴백으로 채운다."""
    if not raw:
        return None
    slug = raw.strip().lower()
    if not slug or not set(slug) <= _SLUG_CHARS:
        return None
    if slug.startswith("-") or slug.endswith("-") or "--" in slug:
        return None
    return slug[:128]
