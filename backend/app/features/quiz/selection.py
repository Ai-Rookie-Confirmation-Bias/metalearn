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


# 정의 키워드 추출 시 조사 제거 ("과정을" → "과정") — 근거 문장은 다른 조사로 활용될 수 있다
_JOSA = re.compile(r"(?:으로|에서|이며|이고|이란|을|를|이|가|은|는|의|로|에|와|과|도|만|란)$")


def _definition_keys(concept: ParsedConcept, name_keys: list[str]) -> set[str]:
    """정의문에서 교차 점수용 내용 키워드. 이름과 겹치는 토큰은 제외(이름 매칭은 전제)."""
    keys: set[str] = set()
    for tok in re.split(r"[^0-9A-Za-z가-힣]+", concept.definition):
        tok = _normalize(_JOSA.sub("", tok))
        if len(tok) >= 2 and not any(tok in nk or nk in tok for nk in name_keys):
            keys.add(tok)
    return keys


def _find_evidence(concept: ParsedConcept, norm_sentences: list[str]) -> list[int]:
    """개념 이름 키워드가 등장하는 문장 = 근거 후보. 관련도 내림차순으로 반환.

    인사말·광고 문장은 개념 키워드가 없어 여기서 자연스럽게 걸러진다.

    이름 매칭만으로는 남의 행을 근거로 잡는다(CPM이 "PERT는 CPM과 달리…" 문장에
    걸림 — QUIZ_TUNING §9-①). 정의 키워드 교차 점수 + 문장이 개념 이름으로 시작하면
    (표에서 그 개념의 행) 가점을 주고, 점수 0인 후보는 더 나은 후보가 있을 때 버린다.
    """
    keys = [k for k in (_normalize(k) for k in _keywords(concept)) if k]
    def_keys = _definition_keys(concept, keys)
    scored: list[tuple[int, int]] = []  # (score, sentence_index)
    for i, ns in enumerate(norm_sentences):
        if not any(k in ns for k in keys):
            continue
        score = sum(1 for d in def_keys if d in ns)
        if any(ns.lstrip("•▪◦∙·※*-—").startswith(k) for k in keys):
            score += 2  # 개념 이름이 주어(행 시작) — 남의 행이 아닐 강한 신호
        scored.append((score, i))
    if any(s > 0 for s, _ in scored):
        scored = [(s, i) for s, i in scored if s > 0]
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [i for _, i in scored]
