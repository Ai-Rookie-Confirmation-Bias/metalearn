"""채점·검증 순수 로직 (기획서 §2.5A/B).

- B. 채점: mcq/cloze/trueFalse 정오, explainBack rubric(키워드 mock / LLM은 호출측)
- A. 검증 규칙: verified=true 조건(source별 근거 ID 필수) — 앱 레벨 게이트

LLM/Solar 호출은 여기서 직접 하지 않는다. explainBack LLM 채점은
grade_explain_back_llm() 인터페이스만 두고, MVP mock은 grade_explain_back_rubric().
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.core.enums import ContentSource


def normalize_text(text: str) -> str:
    """한글/영문 채점용 정규화."""
    text = unicodedata.normalize("NFKC", text or "")
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def grade_exact(user_input: str, expected: str) -> bool:
    return normalize_text(user_input) == normalize_text(expected)


def grade_mcq(user_input: str | int, answer_index: int, options_count: int) -> bool:
    try:
        idx = int(user_input)
    except (TypeError, ValueError):
        return False
    if idx < 0 or idx >= options_count:
        return False
    return idx == answer_index


def cloze_parts(user_input: object, blank_count: int) -> list[str]:
    """user_input(리스트 또는 '답1,답2' 문자열)을 빈칸 수에 맞춘 파트 배열로.

    프론트는 빈칸별 입력을 리스트로 보낸다(콤마 포함 답도 안전). 하위호환으로
    문자열도 받는다: 단일 빈칸이면 통째로, 아니면 콤마 분리.
    """
    if isinstance(user_input, (list, tuple)):
        parts = [str(v).strip() for v in user_input]
    else:
        s = str(user_input or "")
        parts = [s.strip()] if blank_count == 1 else [p.strip() for p in s.split(",")]
    # 길이 정규화(부족分은 빈 문자열, 초과分은 잘라냄)
    if len(parts) < blank_count:
        parts = parts + [""] * (blank_count - len(parts))
    return parts[:blank_count]


def grade_cloze_blanks(user_input: object, blanks: list[str]) -> list[bool]:
    """빈칸별 정규화 정확일치 → 빈칸별 bool 배열. parts[i] ↔ blanks[i]."""
    parts = cloze_parts(user_input, len(blanks))
    return [normalize_text(parts[i]) == normalize_text(expected)
            for i, expected in enumerate(blanks)]


def grade_cloze(user_input: str, blanks: list[str]) -> bool:
    """전체 정오(모든 빈칸 정답일 때만 True). 하위호환용."""
    if not blanks:
        return False
    return all(grade_cloze_blanks(user_input, blanks))


# 빈칸 사이 텍스트가 나열 구분자뿐이면 순서 무관(집합) 문항으로 본다.
_LIST_SEP_RE = re.compile(r"^(?:[\s,，、·/]|및|그리고|또는|and|or)*$", re.IGNORECASE)


def is_enumeration_cloze(text: str, blank_count: int) -> bool:
    """빈칸들이 순서 무관 나열(A, B, C…)인지 — 빈칸 사이가 나열 구분자뿐이면 True.

    예: "핵심 가치는 {{blank}}, {{blank}}, {{blank}}이다" → True(순서 무관).
    빈칸끼리 실제 문장(서로 다른 역할)로 나뉘면 False(위치 채점 유지).
    """
    if blank_count < 2:
        return False
    parts = text.split("{{blank}}")
    if len(parts) != blank_count + 1:
        return False
    return all(_LIST_SEP_RE.match(seg.strip()) for seg in parts[1:-1])


def grade_cloze_set(user_input: object, blanks: list[str]) -> tuple[list[bool], list[str]]:
    """순서 무관 정규화 채점 — 각 입력이 미소진 정답과 정규화 일치하면 True.

    각 정답은 1회만 소진한다(같은 답을 여러 칸에 써서 중복 득점 방지).
    반환: (입력 칸별 정오, 매칭되지 않고 남은 정답 목록 — LLM 의미 채점용).
    """
    parts = cloze_parts(user_input, len(blanks))
    remaining = list(blanks)
    remaining_norm = [normalize_text(b) for b in blanks]
    out: list[bool] = []
    for p in parts:
        np = normalize_text(p)
        if np and np in remaining_norm:
            k = remaining_norm.index(np)
            remaining_norm.pop(k)
            remaining.pop(k)
            out.append(True)
        else:
            out.append(False)
    return out, remaining


@dataclass(frozen=True)
class ExplainBackGrade:
    score: float
    missed_points: list[str]
    comment: str


def grade_explain_back_rubric(user_text: str, rubric: list[str]) -> ExplainBackGrade:
    """Mock rubric 채점: rubric 키워드 포함 비율(오프라인/테스트용).

    프로덕션 explainBack은 Solar LLM 채점으로 교체. 인터페이스(ExplainBackGrade)는 동일.
    """
    if not rubric:
        return ExplainBackGrade(score=0.0, missed_points=[], comment="rubric 없음")
    normalized = normalize_text(user_text)
    hit: list[str] = []
    missed: list[str] = []
    for point in rubric:
        token = normalize_text(point)
        # 키워드 2글자 이상만 매칭(너무 짧은 토큰 제외)
        keywords = [w for w in re.split(r"[\s/·\-]+", token) if len(w) >= 2]
        if not keywords:
            keywords = [token] if token else []
        if any(kw in normalized for kw in keywords):
            hit.append(point)
        else:
            missed.append(point)
    score = len(hit) / len(rubric)
    if score >= 0.8:
        comment = "핵심을 잘 짚었어요."
    elif score >= 0.5:
        comment = "일부 핵심이 빠졌어요."
    else:
        comment = "핵심 개념을 다시 정리해볼까요?"
    return ExplainBackGrade(
        score=round(score, 3),
        missed_points=missed,
        comment=comment,
    )


def can_mark_verified(
    *,
    source: str,
    source_chunk_ids: list,
    external_ref_ids: list,
    data: dict | None = None,
) -> bool:
    """verified=true 가능 여부(앱 레벨 규칙, §2.5A / §4 blocks 주석).

    실제 faithfulness LLM 검증은 별도 파이프라인. 여기서는 '근거 ID 존재' 게이트만.
    """
    if source == ContentSource.BOOK:
        return len(source_chunk_ids) > 0
    if source == ContentSource.AI_PREREQ:
        return len(external_ref_ids) > 0
    if source == ContentSource.ANALOGY:
        return bool(data and data.get("label") == "비유")
    return False
