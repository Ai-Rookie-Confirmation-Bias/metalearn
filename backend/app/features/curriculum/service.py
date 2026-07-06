"""[3.Service] 커리큘럼 빌더 — 개념 그래프 → 학습 순서(챕터/절 계획).

순수 알고리즘 계층: ORM/LLM/DB에 의존하지 않는다. 입력은 개념·선수관계 도메인
DTO, 출력은 정렬된 챕터 계획(ChapterPlan). 영속(chapters/sections INSERT)은
호출측(repository)이 담당한다 → 테스트 쉽고, 팀원 스키마와 충돌하지 않음.

정렬 규칙(기획서 §4 커리큘럼):
  - prerequisite 엣지(from=개념, to=선수)를 위상정렬해 '선수가 먼저' 오게 한다.
  - 이미 아는(예: mastered) 개념은 제외.
  - 사이클/누락 엣지에도 죽지 않게 depth_level을 tiebreak/fallback으로 사용.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConceptNode:
    key: str
    name: str
    source: str = "book"            # book | ai_prereq
    depth_level: int | None = None  # 0=목표(천장), 클수록 기초


@dataclass(frozen=True)
class PrereqEdge:
    """from_key 개념을 이해하려면 to_key(선수)를 먼저 알아야 한다."""

    from_key: str
    to_key: str


@dataclass(frozen=True)
class ChapterPlan:
    order_index: int
    concept_key: str
    title: str
    origin: str  # book | prereq


def _depth_key(node: ConceptNode) -> int:
    # depth_level이 없으면 맨 뒤로(0 취급하면 목표로 오해되므로 큰 값 아님 — 안정 정렬 위해 0).
    return node.depth_level if node.depth_level is not None else 0


def topological_order(
    concepts: list[ConceptNode],
    edges: list[PrereqEdge],
) -> list[ConceptNode]:
    """선수지식이 먼저 오도록 위상정렬. 사이클은 depth 순 fallback으로 안전 처리.

    Kahn 알고리즘. 동점(진입차수 동일)일 때는 depth_level 내림차순(기초 먼저) →
    같은 depth면 원래 입력 순서를 유지(안정).
    """
    by_key = {c.key: c for c in concepts}
    # prerequisite(to_key)가 dependent(from_key)보다 먼저 나와야 하므로,
    # 그래프 방향을 to_key -> from_key 로 두고 위상정렬한다.
    indeg: dict[str, int] = {k: 0 for k in by_key}
    adj: dict[str, list[str]] = {k: [] for k in by_key}
    seen_edges: set[tuple[str, str]] = set()
    for e in edges:
        if e.from_key not in by_key or e.to_key not in by_key:
            continue
        if e.from_key == e.to_key:
            continue
        pair = (e.to_key, e.from_key)
        if pair in seen_edges:
            continue
        seen_edges.add(pair)
        adj[e.to_key].append(e.from_key)
        indeg[e.from_key] += 1

    def ready_sort_key(k: str) -> tuple[int, int]:
        node = by_key[k]
        # depth 큰(기초) 것 먼저 → 음수로 뒤집고, 안정성 위해 원래 인덱스 tiebreak
        return (-_depth_key(node), _input_index[k])

    _input_index = {c.key: i for i, c in enumerate(concepts)}

    frontier = sorted([k for k, d in indeg.items() if d == 0], key=ready_sort_key)
    ordered: list[ConceptNode] = []
    while frontier:
        k = frontier.pop(0)
        ordered.append(by_key[k])
        for nxt in adj[k]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                frontier.append(nxt)
        frontier.sort(key=ready_sort_key)

    # 사이클로 남은 노드는 depth 순으로 뒤에 붙임(누락 방지).
    if len(ordered) < len(concepts):
        remaining = [c for c in concepts if c not in ordered]
        remaining.sort(key=lambda c: (-_depth_key(c), _input_index[c.key]))
        ordered.extend(remaining)
    return ordered


def build_curriculum(
    concepts: list[ConceptNode],
    edges: list[PrereqEdge],
    known_keys: set[str] | None = None,
) -> list[ChapterPlan]:
    """개념 그래프 → 챕터 계획 리스트.

    known_keys: 진단에서 '안다'고 판정돼 스킵할 개념(예: floor 아래). 제외된다.
    origin: 책 개념은 'book', 책 밖 선행(ai_prereq)은 'prereq'.
    """
    known = known_keys or set()
    ordered = topological_order(concepts, edges)
    plans: list[ChapterPlan] = []
    idx = 1
    for node in ordered:
        if node.key in known:
            continue
        plans.append(
            ChapterPlan(
                order_index=idx,
                concept_key=node.key,
                title=node.name,
                origin="prereq" if node.source == "ai_prereq" else "book",
            )
        )
        idx += 1
    return plans
