"""③④ 예산·유형 계획 (docs/QUIZ.md §2-④). 순수 함수.

목차 예산 = clamp(출제가능 개념수 × 계수, min, max).
개념당: 바닥 1문항(커버리지) + 중요도 순으로 추가 + 유형은 형태 후보 안에서 배분.
"""
import re
from collections import Counter

from app.features.quiz.schemas import (
    FORM_TYPE_CANDIDATES,
    ChunkWorkOrder,
    ConceptPlan,
    ContentForm,
    ParsedDocument,
    QuizGenConfig,
    QuizType,
)
from app.features.quiz.selection import ChunkSelection, EligibleConcept


def classify_form(definition: str, evidence_text: str) -> ContentForm:
    """원문 형태 분류 — 규칙 기반 1차 판정 (LLM 아님 → 결정적).

    docs/QUIZ.md §2-⑤ 표의 판정 신호를 그대로 코드로 옮긴 것.
    """
    text = f"{definition} {evidence_text}"
    # sequence는 근거 원문에 실제 절차 나열(화살표류 구분자 2회 이상: A→B→C)이
    # 있을 때만. "단계"·"순서" 키워드 매칭은 개념 이름만으로 오분류를 일으켜 제거
    # (예: "개발 단계별 인월 수" — docs/QUIZ_TUNING.md §5-①).
    if len(re.findall(r"(?:→|➔|▶|->)", evidence_text)) >= 2:
        return "sequence"
    # 나열: 쉼표/가운뎃점 구분 항목 3개 이상, 혹은 "N가지" 패턴
    if re.search(r"\d+\s*가지", text) or len(re.findall(r"[,·]", evidence_text)) >= 3:
        return "enumeration"
    if re.search(r"(반면|달리|비해|vs|대비)", text):
        return "contrast"
    return "definition"


def importance_score(
    concept_name: str,
    multi_chunk_counts: Counter,
    prereq_ref_counts: Counter,
    exam_frequency: dict[str, int] | None = None,
) -> float:
    """중요도: 기출 빈도 > 다조각 등장 > 선수 참조 수 (가중 합)."""
    score = 0.0
    if exam_frequency:
        score += exam_frequency.get(concept_name, 0) * 10.0
    score += (multi_chunk_counts[concept_name] - 1) * 3.0  # 2조각째부터 가점
    score += prereq_ref_counts[concept_name] * 1.0
    return score


def plan_document(
    doc: ParsedDocument,
    selections: dict[int, ChunkSelection],  # chunk_index → 선별 결과
    config: QuizGenConfig,
    exam_frequency: dict[str, int] | None = None,
    type_ratio: dict[QuizType, float] | None = None,
) -> list[ChunkWorkOrder]:
    """문서 전체의 생성 작업 지시 목록. 호출 전에 예산을 확정한다."""
    ratio = type_ratio or config.type_ratio

    # 중요도 신호 수집 (문서 전역)
    multi_chunk = Counter()
    prereq_refs = Counter()
    for chunk in doc.chunks:
        for c in chunk.concepts:
            multi_chunk[c.name] += 1
            for p in c.prereqs:
                prereq_refs[p] += 1

    orders: list[ChunkWorkOrder] = []
    for toc in doc.tocs:
        toc_selections = [
            selections[ci] for ci in toc.chunk_indexes if ci in selections
        ]
        orders.extend(
            _plan_toc(
                doc, toc.index, toc_selections, config, ratio,
                multi_chunk, prereq_refs, exam_frequency,
            )
        )
    return orders


def _plan_toc(
    doc: ParsedDocument,
    toc_index: int,
    toc_selections: list[ChunkSelection],
    config: QuizGenConfig,
    ratio: dict[QuizType, float],
    multi_chunk: Counter,
    prereq_refs: Counter,
    exam_frequency: dict[str, int] | None,
) -> list[ChunkWorkOrder]:
    chunk_by_index = {c.index: c for c in doc.chunks}

    # 목차 내 유니크 개념 (여러 조각 등장 시 근거 문장이 가장 많은 조각 채택 = dedup)
    best: dict[str, tuple[int, EligibleConcept]] = {}
    for sel in toc_selections:
        for ec in sel.eligible:
            cur = best.get(ec.concept.name)
            if cur is None or len(ec.evidence_sentence_ids) > len(cur[1].evidence_sentence_ids):
                best[ec.concept.name] = (sel.chunk_index, ec)

    n_concepts = len(best)
    if n_concepts == 0:
        return []
    budget = max(config.toc_min, min(config.toc_max, round(n_concepts * config.toc_multiplier)))
    budget = round(budget * config.overgen_ratio)

    # 중요도 내림차순으로 문항 슬롯 배분: 예산 안에서 전원 1개(커버리지 바닥),
    # 개념이 예산보다 많으면 중요도 상위부터. 남는 예산은 중요도순 +1 (상한까지).
    ranked = sorted(
        best.items(),
        key=lambda kv: importance_score(kv[0], multi_chunk, prereq_refs, exam_frequency),
        reverse=True,
    )
    alloc: dict[str, int] = {
        name: (1 if i < budget else 0) for i, (name, _) in enumerate(ranked)
    }
    remaining = budget - sum(alloc.values())
    level = 2
    while remaining > 0 and level <= config.per_concept_max:
        for name, _ in ranked:
            if remaining <= 0:
                break
            if alloc[name] == level - 1:
                alloc[name] = level
                remaining -= 1
        level += 1

    # 유형 배분: 형태 후보 안에서, 목차 전체가 ratio에 근접하도록 라운드로빈
    type_quota = {t: max(1, round(sum(alloc.values()) * r)) for t, r in ratio.items()}
    type_used: Counter = Counter()

    plans_by_chunk: dict[int, list[ConceptPlan]] = {}
    for name, (chunk_index, ec) in ranked:
        chunk = chunk_by_index[chunk_index]
        evidence_text = " ".join(
            chunk.raw_text[chunk.sentences[i].start : chunk.sentences[i].end]
            for i in ec.evidence_sentence_ids[:5]
        )
        form = classify_form(ec.concept.definition, evidence_text)
        candidates = FORM_TYPE_CANDIDATES[form]
        types = _pick_types(candidates, alloc[name], type_quota, type_used)
        if not types:  # 예산에서 밀린 개념 — 생성 지시에서 제외
            continue
        plans_by_chunk.setdefault(chunk_index, []).append(
            ConceptPlan(
                name=name,
                definition=ec.concept.definition,
                form=form,
                types=types,
                evidence_sentence_ids=ec.evidence_sentence_ids,
            )
        )

    return [
        ChunkWorkOrder(toc_index=toc_index, chunk_index=ci, concept_plans=plans)
        for ci, plans in sorted(plans_by_chunk.items())
    ]


def _pick_types(
    candidates: list[QuizType],
    count: int,
    quota: dict[QuizType, float],
    used: Counter,
) -> list[QuizType]:
    """후보 유형 중 쿼터 여유가 가장 큰 것부터. 같은 개념엔 유형 중복 없이."""
    picked: list[QuizType] = []
    for _ in range(count):
        avail = [t for t in candidates if t not in picked]
        if not avail:
            break
        t = max(avail, key=lambda t: quota.get(t, 0) - used[t])
        picked.append(t)
        used[t] += 1
    return picked
