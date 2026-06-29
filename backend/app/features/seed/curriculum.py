"""진단 결과 → 개인 맞춤 커리큘럼(학습 로드맵) 생성.

- 약점 concept를 문서 순서대로 앞에 배치 (보강 우선)
- 나머지 concept는 원래 순서 유지
- 세션별 문제 생성은 이후 learning 단계에서 (여기선 로드맵만)
"""
from __future__ import annotations

from app.features.materials.schemas import ConceptEntry, DocumentSkeleton, TocEntry
from app.features.seed.weakness_utils import weakness_id_set


def _chapter_for_page(toc: list[TocEntry], page: int) -> str | None:
    for entry in toc:
        if entry.start_page <= page <= entry.end_page:
            return entry.id
    return None


def build_curriculum_units(
    concepts_in_range: list[str],
    weaknesses: list,
    skeleton: DocumentSkeleton,
) -> list[dict]:
    weakness_set = weakness_id_set(weaknesses)
    weak_ordered = [c for c in concepts_in_range if c in weakness_set]
    rest_ordered = [c for c in concepts_in_range if c not in weakness_set]
    ordered_ids = weak_ordered + rest_ordered

    concept_map: dict[str, ConceptEntry] = {c.id: c for c in skeleton.concepts}
    units: list[dict] = []

    for idx, concept_id in enumerate(ordered_ids, start=1):
        concept = concept_map.get(concept_id)
        if concept is None:
            continue
        page = concept.page_numbers[0]
        chapter_id = _chapter_for_page(skeleton.toc, page)
        units.append(
            {
                "order": idx,
                "concept_id": concept_id,
                "title": concept.title,
                "page_numbers": concept.page_numbers,
                "chunk_ids": concept.chunk_ids,
                "chapter_id": chapter_id,
                "priority": "weakness" if concept_id in weakness_set else "standard",
                "status": "pending",
            }
        )

    return units


def build_chapter_groups(units: list[dict], toc: list[TocEntry]) -> list[dict]:
    """UI용 챕터별 그룹 (units 순서 유지)."""
    toc_titles = {t.id: t.title for t in toc}
    groups: list[dict] = []
    current_chapter: str | None = None

    for unit in units:
        ch = unit.get("chapter_id")
        if ch != current_chapter:
            current_chapter = ch
            groups.append(
                {
                    "chapter_id": ch,
                    "chapter_title": toc_titles.get(ch, ch or "기타"),
                    "units": [],
                }
            )
        groups[-1]["units"].append(unit)

    return groups


GOAL_LABELS = {
    "exam": "시험 대비",
    "concept_understanding": "개념 이해",
    "problem_solving": "문제 풀이",
    "skim": "훑어보기",
}


def enrich_curriculum_units_local(
    units: list[dict],
    weaknesses: list,
    learning_goal: str | None,
) -> list[dict]:
    """LLM 실패 시에도 읽을 만한 로드맵 문구 제공."""
    weakness_set = weakness_id_set(weaknesses)
    goal = GOAL_LABELS.get(learning_goal or "", learning_goal or "학습")

    enriched: list[dict] = []
    for unit in units:
        title = unit.get("title", unit.get("concept_id", ""))
        is_weak = unit.get("concept_id") in weakness_set or unit.get("priority") == "weakness"
        if is_weak:
            summary = f"진단에서 보강이 필요한 개념입니다 — {title}"
            focus = f"{goal} 관점에서 원문을 읽고 핵심을 직접 설명해 보세요."
        else:
            summary = f"{title} — 순서대로 학습합니다."
            focus = "앞 단원과 연결하며 원문 기반으로 이해해 보세요."
        enriched.append({**unit, "summary": summary, "focus": focus})
    return enriched
