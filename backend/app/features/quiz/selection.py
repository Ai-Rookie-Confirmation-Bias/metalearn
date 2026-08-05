"""② 출제 대상 선별 (docs/QUIZ.md §2-②). 순수 함수.

파서는 원문을 무손실 보존하므로(인사말·광고 포함) 정제는 여기서 한다.
산출 = 개념별 근거 문장 후보 + 출제 불가 사유 로그.
"""
import re
from dataclasses import dataclass, field

from app.features.quiz.schemas import ParsedChunk, ParsedConcept

# 비전 필요 그림 offset 앞뒤로 이만큼 겹치는 문장은 "그림 없이는 불완전"으로 본다
VISION_EXCLUSION_RADIUS = 120


@dataclass
class EligibleConcept:
    concept: ParsedConcept
    evidence_sentence_ids: list[int]  # 조각 내 문장 인덱스


@dataclass
class ChunkSelection:
    chunk_index: int
    eligible: list[EligibleConcept] = field(default_factory=list)
    excluded_concepts: dict[str, str] = field(default_factory=dict)  # name → 사유


def _normalize(text: str) -> str:
    """OCR로 붙은 띄어쓰기·개행을 무시하고 비교하기 위한 정규화."""
    return re.sub(r"\s+", "", text)


def _keywords(concept: ParsedConcept) -> list[str]:
    """개념 이름에서 매칭용 키워드 추출.

    괄호 병기(영문 약어)는 별도 키워드로. 원문이 접미사 없이 언급하는 경우
    ("폭포수 모형" → 표에는 "폭포수")를 잡기 위해 첫 토큰도 후보에 넣는다.
    """
    name = concept.name
    kws = [name]
    for inner in re.findall(r"[(（]([^)）]+)[)）]", name):
        kws.append(inner)
    kws.append(re.sub(r"\s*[(（][^)）]*[)）]", "", name))
    first = name.split()[0] if name.split() else ""
    if len(first) >= 3:  # 2자 첫 토큰("자료" 등)은 오탐이 많아 제외
        kws.append(first)
    return [k.strip() for k in kws if len(k.strip()) >= 2]


def select_chunk(chunk: ParsedChunk) -> ChunkSelection:
    sel = ChunkSelection(chunk_index=chunk.index)

    # 비전 필요 그림 주변 문장 → 제외 집합
    vision_banned: set[int] = set()
    for f in chunk.figures:
        if not f.needs_vision:
            continue
        lo, hi = f.offset - VISION_EXCLUSION_RADIUS, f.offset + VISION_EXCLUSION_RADIUS
        for i, a in enumerate(chunk.sentences):
            if a.start < hi and a.end > lo:
                vision_banned.add(i)

    norm_sentences = [
        _normalize(chunk.raw_text[a.start : a.end]) for a in chunk.sentences
    ]

    for concept in chunk.concepts:
        hits = _find_evidence(concept, norm_sentences)
        usable = [i for i in hits if i not in vision_banned]
        if usable:
            sel.eligible.append(
                EligibleConcept(concept=concept, evidence_sentence_ids=usable)
            )
        elif hits:
            sel.excluded_concepts[concept.name] = "근거 문장이 전부 비전 필요 그림에 의존"
        else:
            sel.excluded_concepts[concept.name] = "원문에서 근거 문장을 찾지 못함"

    return sel


def _find_evidence(concept: ParsedConcept, norm_sentences: list[str]) -> list[int]:
    """개념 이름 키워드가 등장하는 문장 = 근거 후보.

    인사말·광고 문장은 개념 키워드가 없어 여기서 자연스럽게 걸러진다.
    """
    keys = [_normalize(k) for k in _keywords(concept)]
    hits: list[int] = []
    for i, ns in enumerate(norm_sentences):
        if any(k and k in ns for k in keys):
            hits.append(i)
    return hits
