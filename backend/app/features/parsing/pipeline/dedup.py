"""10단계 — 개념 중복 정리. Solar 4회 이하.

**3중 방어.** 하나로는 안 된다.

  ① 이름 정규화   공백·괄호 제거 후 비교 (11단계 저장에서 이미 적용)
                  "일계도함수 / 일계 도함수"는 임베딩으로 0.75~0.81이라
                  문턱에 절대 안 걸린다 — 표면 중복은 정규화만 잡을 수 있다.

  ② 임베딩 최근접  0.92 이상이면 LLM 없이 즉시 병합

  ③ LLM 배치 판정  0.85~0.92 구간만 50개씩 묶어 물어본다
                  실측상 진짜 중복이 이 구간에 별개 개념과 섞여 분포해
                  문턱 하나로는 분리가 불가능하다.

병합할 때 **원문 출처를 전부 이관한다** — repository.merge_concepts 참고.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from app.core.config import settings
from app.core.llm.solar import solar_client
from app.features.parsing.models import Concept
from app.features.parsing.prompts import dedup as prompt
from app.features.parsing.repository import ParsingRepository

_log = logging.getLogger("uvicorn.error")


@dataclass
class DedupResult:
    candidate_pairs: int = 0
    auto_merged: int = 0    # ② 임베딩 문턱으로 자동 병합
    judged_merged: int = 0  # ③ LLM 판정으로 병합
    llm_calls: int = 0      # ③에서 실제로 부른 횟수
    links_preserved: int = 0  # 병합하며 살려낸 원문 링크 수

    @property
    def total_merged(self) -> int:
        return self.auto_merged + self.judged_merged


def _rank(concept: Concept) -> tuple:
    """병합 시 남길 쪽: 교재 출처 우선 → 이름 짧은 쪽 → id(결정적 타이브레이크).

    이름이 짧은 쪽을 남기는 이유: "DRM"과 "디지털 저작권 관리(DRM)"가
    같다고 판정되면 짧은 표기가 개념명으로 더 쓸모 있다.
    """
    return (0 if concept.source == "book" else 1, len(concept.name), str(concept.id))


async def run(repo: ParsingRepository, document_id: uuid.UUID) -> DedupResult:
    """문서 하나의 개념 중복을 정리한다."""
    result = DedupResult()

    pairs = repo.find_similar_pairs(
        document_id=document_id,
        min_sim=settings.DEDUP_CANDIDATE_SIM_THRESHOLD,
        limit=settings.DEDUP_MAX_PAIRS,
    )
    if not pairs:
        _log.info("중복 판정: 후보쌍 없음")
        return result
    result.candidate_pairs = len(pairs)

    # ② 문턱 이상은 묻지 않고 병합, 나머지만 LLM에게 넘긴다.
    auto: list[tuple[uuid.UUID, uuid.UUID]] = []
    to_judge: list[tuple[Concept, Concept, float]] = []
    for a, b, sim in pairs:
        if sim >= settings.CONCEPT_DEDUP_SIM_THRESHOLD:
            auto.append((a.id, b.id))
        else:
            to_judge.append((a, b, sim))

    # ③ LLM 배치 판정
    judged: list[tuple[uuid.UUID, uuid.UUID]] = []
    batch_size = settings.DEDUP_JUDGE_BATCH_SIZE
    for i in range(0, len(to_judge), batch_size):
        batch = to_judge[i : i + batch_size]
        try:
            raw = await solar_client.generate_json(
                prompt.build_prompt(
                    [(a.name, a.definition or "", b.name, b.definition or "", s)
                     for a, b, s in batch]
                ),
                system=prompt.SYSTEM,
            )
        except Exception as exc:  # noqa: BLE001 — 청소 실패는 비치명
            _log.warning("중복 판정 실패, 배치 건너뜀: %s", exc)
            continue
        result.llm_calls += 1
        for index in raw.get("same") or []:
            if isinstance(index, int) and 0 <= index < len(batch):
                a, b, _ = batch[index]
                judged.append((a.id, b.id))

    result.auto_merged = _merge_all(repo, auto, result)
    result.judged_merged = _merge_all(repo, judged, result)

    _log.info(
        "중복 정리: 후보 %d쌍 → 자동 병합 %d · LLM 판정 병합 %d "
        "(살려낸 원문 링크 %d개, LLM 호출 %d회)",
        result.candidate_pairs, result.auto_merged, result.judged_merged,
        result.links_preserved, result.llm_calls,
    )
    return result


def _merge_all(
    repo: ParsingRepository,
    pairs: list[tuple[uuid.UUID, uuid.UUID]],
    result: DedupResult,
) -> int:
    """체인 병합(A~B, B~C)을 따라가며 실제 병합을 수행한다."""
    redirect: dict[uuid.UUID, uuid.UUID] = {}

    def final(cid: uuid.UUID) -> uuid.UUID:
        while cid in redirect:
            cid = redirect[cid]
        return cid

    merged = 0
    for a_id, b_id in pairs:
        ka, kb = final(a_id), final(b_id)
        if ka == kb:
            continue
        a, b = repo.get_concept(ka), repo.get_concept(kb)
        if a is None or b is None:
            continue
        keep, drop = (a, b) if _rank(a) <= _rank(b) else (b, a)
        _log.debug("중복 병합: %r ← %r", keep.name, drop.name)
        result.links_preserved += repo.merge_concepts(keep=keep, drop=drop)
        redirect[drop.id] = keep.id
        merged += 1
    return merged
