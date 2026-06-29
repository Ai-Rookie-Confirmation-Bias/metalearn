"""튜터 프롬프트·Solar fallback."""
from __future__ import annotations

import json
import logging

from app.core.groundedness import verify_generated_content
from app.core.llm.base import LLMClient

logger = logging.getLogger(__name__)


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("JSON object expected")
    return data


def chunks_text(chunks: list) -> str:
    if not chunks:
        return "(원문 없음)"
    return "\n\n---\n\n".join(
        f"[p.{c.page_number}]\n{c.text[:1200]}" for c in chunks[:3]
    )


def fallback_question(title: str, focus: str | None) -> str:
    focus_part = f" ({focus})" if focus else ""
    return (
        f"'{title}'{focus_part} 개념을 자신의 말로 설명해 보세요. "
        "핵심 원리와 왜 중요한지 포함해 주세요."
    )


def fallback_judge(user_response: str, title: str) -> dict:
    stripped = user_response.strip()
    ok = len(stripped) >= 30
    if ok:
        feedback = f"'{title}'에 대한 이해가 드러납니다. 핵심을 짚어 설명했어요."
    else:
        feedback = "답변이 짧습니다. 핵심 개념을 조금 더 구체적으로 설명해 보세요."
    return {"correct": ok, "feedback": feedback}


def fallback_missing_concept(concept: str) -> dict:
    return {
        "missing_concept": concept,
        "reason": "추론 불가",
        "suggested_review": "원문 재독",
    }


def fallback_hint_1(title: str) -> str:
    return (
        f"'{title}'의 정의를 떠올려 보세요. "
        "관련 키워드 2~3개를 먼저 적어 보면 도움이 됩니다."
    )


def fallback_hint_2(title: str, chunks: list) -> str:
    preview = chunks[0].text[:200].replace("\n", " ") if chunks else title
    return f"힌트: 원문에서 '{preview[:80]}...' 부분과 연결해 보세요."


def fallback_answer_reveal(title: str, unit_content: str | None, chunks: list) -> str:
    if unit_content and unit_content.strip():
        return f"[{title}]\n\n{unit_content[:1500]}"
    if chunks:
        return f"[{title}]\n\n{chunks[0].text[:1500]}"
    return f"[{title}] 원문을 다시 읽고 핵심 문장을 정리해 보세요."


async def generate_question(
    llm: LLMClient,
    *,
    title: str,
    focus: str | None,
    chunks: list,
) -> str:
    prompt = f"""당신은 메타인지 튜터입니다.
학습 주제: {title}
핵심 포인트: {focus or "없음"}
참고 원문:
{chunks_text(chunks)}

학습자가 이 개념을 실제로 이해했는지 확인하는
개방형 역질문 1개를 만드세요.
답을 주지 말고, 오직 질문만 출력하세요."""

    for attempt in range(2):
        try:
            raw = await llm.generate(prompt)
            question = raw.strip()
            if not question:
                continue

            result = await verify_generated_content(question, chunks)
            if result.is_grounded:
                return question

            logger.warning(
                "역질문 groundedness 실패 (%s, attempt %d): %s",
                title,
                attempt + 1,
                result.reason,
            )
            if attempt == 1:
                logger.warning("역질문 검증 실패 — unverified 사용: %s", title)
                return question
        except Exception:
            logger.exception("Solar 역질문 생성 실패")

    return fallback_question(title, focus)


async def judge_response(
    llm: LLMClient,
    *,
    concept: str,
    question: str,
    user_response: str,
    chunks: list,
) -> dict:
    prompt = f"""학습 주제: {concept}
질문: {question}
학습자 답변: {user_response}
원문 근거:
{chunks_text(chunks)}

답변이 핵심 개념을 이해했는지 판단하세요.
JSON으로만 응답: {{"correct": true/false, "feedback": "한 줄 피드백"}}"""
    try:
        raw = await llm.generate(prompt, json_mode=True)
        data = _parse_json(raw)
        correct = bool(data.get("correct"))
        feedback = str(data.get("feedback") or "").strip()
        if feedback:
            return {"correct": correct, "feedback": feedback}
    except Exception:
        logger.exception("Solar 정오 판단 실패")
    return fallback_judge(user_response, concept)


async def infer_missing_concept(
    llm: LLMClient,
    *,
    question: str,
    user_response: str,
    concept: str,
    chunks: list,
) -> dict:
    prompt = f"""학습자가 다음 문제를 틀렸습니다.
개념: {concept}
질문: {question}
학습자 답변: {user_response}
원문 근거: {chunks_text(chunks)}

오답 패턴을 분석해서 어떤 하위 개념이 부족한지 추론하세요.
JSON으로만 응답:
{{"missing_concept": "...", "reason": "...", "suggested_review": "..."}}"""
    try:
        raw = await llm.generate(prompt, json_mode=True)
        data = _parse_json(raw)
        missing_concept = str(data.get("missing_concept") or "").strip()
        reason = str(data.get("reason") or "").strip()
        suggested_review = str(data.get("suggested_review") or "").strip()
        if missing_concept and reason:
            return {
                "missing_concept": missing_concept,
                "reason": reason,
                "suggested_review": suggested_review or "원문 재독",
            }
    except Exception:
        logger.exception("Solar missing_concept 추론 실패")
    return fallback_missing_concept(concept)


async def generate_hint_1(
    llm: LLMClient,
    *,
    title: str,
    question: str,
    user_response: str,
) -> str:
    prompt = (
        f"학습 주제 '{title}'에 대해 학습자가 틀렸습니다.\n"
        f"질문: {question}\n"
        f"학습자 답변: {user_response}\n"
        "정답을 주지 말고, 방향을 제시하는 짧은 힌트 1~2문장만 출력하세요."
    )
    try:
        raw = await llm.generate(prompt)
        hint = raw.strip()
        if hint:
            return hint
    except Exception:
        logger.exception("Solar hint_1 생성 실패")
    return fallback_hint_1(title)


async def generate_hint_2(
    llm: LLMClient,
    *,
    title: str,
    question: str,
    user_response: str,
    chunks: list,
) -> str:
    prompt = f"""학습 주제: {title}
질문: {question}
학습자 답변: {user_response}
참고 원문:
{chunks_text(chunks)}

학습자가 틀렸습니다. hint_1보다 더 구체적인 힌트 1~2문장을 주세요.
정답을 직접 말하지 마세요."""
    try:
        raw = await llm.generate(prompt)
        hint = raw.strip()
        if hint:
            return hint
    except Exception:
        logger.exception("Solar hint_2 생성 실패")
    return fallback_hint_2(title, chunks)


async def infer_prerequisite_concept(
    llm: LLMClient,
    *,
    parent_concept: str,
    missing_concept: str,
) -> dict:
    """학습자가 막힌 개념에서 필요한 선수 개념을 추론한다."""
    prompt = f"""학습자가 '{parent_concept}' 개념을 학습하다 막혔습니다.
부족한 하위 개념: {missing_concept}

이 학습자에게 지금 당장 필요한 선수 개념 1개를 추론하세요.

조건:
- '{parent_concept}'보다 더 기초적이어야 함
- 이 선수 개념을 알면 '{missing_concept}'를 이해할 수 있어야 함
- 더 이상 쪼갤 수 없는 최소 단위의 기초 개념이라면 is_foundational=true

JSON으로만 응답:
{{"title": "선수 개념 제목", "why": "왜 이 개념이 필요한지 한 줄", "is_foundational": false}}"""
    try:
        raw = await llm.generate(prompt, json_mode=True)
        data = _parse_json(raw)
        title = str(data.get("title") or "").strip()
        why = str(data.get("why") or "").strip()
        is_foundational = bool(data.get("is_foundational", False))
        if title:
            return {"title": title, "why": why, "is_foundational": is_foundational}
    except Exception:
        logger.exception("prerequisite 개념 추론 실패")
    return {
        "title": missing_concept,
        "why": f"'{parent_concept}' 이해에 필요한 기초 개념",
        "is_foundational": False,
    }


async def generate_prereq_question(
    llm: LLMClient,
    *,
    title: str,
    why: str,
) -> str:
    """선수 개념(PDF 없음)에 대한 역질문 생성 — LLM 자체 지식 사용."""
    prompt = f"""당신은 메타인지 튜터입니다.
학습 주제: {title}
이 개념이 필요한 이유: {why}

학습자가 '{title}' 개념을 실제로 이해하는지 확인하는
개방형 역질문 1개를 만드세요.
답을 주지 말고, 오직 질문만 출력하세요."""
    try:
        raw = await llm.generate(prompt)
        question = raw.strip()
        if question:
            return question
    except Exception:
        logger.exception("prerequisite 역질문 생성 실패")
    return fallback_question(title, why)


async def generate_prereq_answer_reveal(
    llm: LLMClient,
    *,
    title: str,
    question: str,
) -> str:
    """선수 개념 정답 해설 — PDF 없이 LLM 자체 지식으로 설명."""
    prompt = f"""학습 주제: {title}
질문: {question}

학습자에게 '{title}' 개념을 명확하게 설명해 주세요.
핵심 원리를 3~5문장으로 한국어로 설명하세요."""
    try:
        raw = await llm.generate(prompt)
        answer = raw.strip()
        if answer:
            return answer
    except Exception:
        logger.exception("prerequisite answer_reveal 생성 실패")
    return f"[{title}] 개념을 다시 한 번 정리해 보세요."


async def generate_answer_reveal(
    llm: LLMClient,
    *,
    title: str,
    question: str,
    chunks: list,
    unit_content: str | None,
) -> str:
    prompt = f"""학습 주제: {title}
질문: {question}
참고 원문:
{chunks_text(chunks)}

학습자에게 원문 근거 기반으로 개념을 명확히 설명해 주세요.
3~5문장, 한국어."""
    try:
        raw = await llm.generate(prompt)
        answer = raw.strip()
        if answer:
            return answer
    except Exception:
        logger.exception("Solar answer_reveal 생성 실패")
    return fallback_answer_reveal(title, unit_content, chunks)
