"""LLM이 객관식 내용을 inverse/cloze로 잘못 분류할 때 mcq로 교정.

역질문/빈칸으로 분류됐지만 본문에 1~4번 보기가 있으면 → mcq 변환.
→ 서술형 UI + LLM 채점(토큰 낭비) 방지.
"""
from __future__ import annotations

import re

from app.features.diagnostic.schemas import ClozeDraft, InverseDraft, McqDraft, QuizDraft

# 1. / 1) / ① 형태의 보기 줄
_OPTION_LINE = re.compile(
    r"^\s*(?:([1-4])[.)）]\s*|([①②③④])\s*)(.+)$",
    re.MULTILINE,
)
_CIRCLE_TO_IDX = {"①": 0, "②": 1, "③": 2, "④": 3}


def _parse_numbered_options(question: str) -> tuple[str, list[str]] | None:
    """question 본문에서 번호 매긴 보기 4개를 추출. 없으면 None."""
    lines = question.splitlines()
    stem_parts: list[str] = []
    options: list[str] = []
    in_options = False

    for line in lines:
        m = _OPTION_LINE.match(line)
        if m:
            in_options = True
            options.append(m.group(3).strip())
        elif not in_options:
            if line.strip():
                stem_parts.append(line.strip())
        elif in_options and line.strip() and options:
            options[-1] += " " + line.strip()

    if len(options) < 4:
        return None
    stem = "\n".join(stem_parts).strip() or question.split("1.")[0].strip()
    return stem, options[:4]


def _guess_answer_index(expected: str, options: list[str]) -> int:
    """expected_answer에서 정답 보기 인덱스 추정."""
    exp = expected.strip()
    exp_lower = exp.lower()

    # expected가 보기 문장과 거의 같으면 그 인덱스 (예: "1번과 2번 모두 정답")
    for i, opt in enumerate(options):
        if opt.strip() == exp or exp in opt or opt.strip() in exp:
            return i
        if opt.strip().lower() in exp_lower or exp_lower in opt.strip().lower():
            return i

    # "1번", "2번" 단일 번호
    nums = re.findall(r"([1-4])\s*번", exp)
    if len(nums) == 1:
        return int(nums[0]) - 1
    # "1번과 2번 모두" → "모두" 포함 보기 찾기
    if len(nums) >= 2 or "모두" in exp:
        for i, opt in enumerate(options):
            if "모두" in opt or "both" in opt.lower():
                return i

    return 0


def looks_like_mcq(question: str) -> bool:
    parsed = _parse_numbered_options(question)
    return parsed is not None


def coerce_quiz_draft(draft: QuizDraft) -> QuizDraft:
    """inverse/cloze인데 본문이 4지선다 형태면 mcq로 교정."""
    if isinstance(draft, McqDraft):
        return draft

    parsed = _parse_numbered_options(draft.question)
    if parsed is None:
        return draft

    stem, options = parsed
    expected = draft.expected_answer
    return McqDraft(
        qtype="mcq",
        question=stem or draft.question,
        options=options,
        answer_index=_guess_answer_index(expected, options),
        explanation=draft.explanation,
    )
