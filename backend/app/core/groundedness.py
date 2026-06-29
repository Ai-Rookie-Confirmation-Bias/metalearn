"""생성 텍스트·concept chunk의 원문 근거 검증."""
from __future__ import annotations

import json
import logging
import math
import re
import uuid

from pydantic import BaseModel, Field

from app.core.llm.factory import get_llm_client
from app.core.vector_store import ChunkResult, search_similar_chunks

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.4


class GroundednessResult(BaseModel):
    is_grounded: bool
    similarity_score: float | None = None
    reason: str | None = None
    confidence: float | None = None
    unmatched_chunk_ids: list[str] = Field(default_factory=list)


def log_concept_groundedness(concept_id: str, result: GroundednessResult) -> None:
    score = result.similarity_score or 0.0
    status = "통과" if result.is_grounded else "재검토 필요"
    logger.info(
        "groundedness 검증 결과: score=%.2f concept=%s → %s",
        score,
        concept_id,
        status,
    )


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("JSON object expected")
    return data


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _chunks_to_text(chunks: list) -> str:
    if not chunks:
        return "(원문 없음)"
    parts: list[str] = []
    for c in chunks[:5]:
        if hasattr(c, "text") and getattr(c, "text", None):
            parts.append(str(c.text)[:2000])
        elif hasattr(c, "content") and getattr(c, "content", None):
            parts.append(str(c.content)[:2000])
        else:
            parts.append(str(c)[:2000])
    return "\n\n---\n\n".join(parts)


def _title_keywords(title: str) -> list[str]:
    cleaned = title.strip()
    if ":" in cleaned:
        cleaned = cleaned.split(":", 1)[1].strip()
    cleaned = re.sub(r"^단원\s*\d+\s*", "", cleaned)
    words: list[str] = []
    for part in re.split(r"[\s/·\-]+", cleaned):
        token = part.strip(".,()[]\"'")
        if len(token) >= 2:
            words.append(token)
    return words[:8]


def _title_keyword_match(title: str, chunk_text: str) -> bool:
    keywords = _title_keywords(title)
    if not keywords:
        return False
    lower = chunk_text.lower()
    matched = sum(1 for kw in keywords if kw.lower() in lower)
    return matched >= max(1, len(keywords) // 2)


async def _similarity_fallback(content: str, chunks: list) -> GroundednessResult:
    chunk_text = _chunks_to_text(chunks)
    if not content.strip() or not chunk_text.strip() or chunk_text == "(원문 없음)":
        return GroundednessResult(
            is_grounded=False,
            similarity_score=0.0,
            reason="원문 chunk 없음",
            confidence=0.0,
        )
    try:
        llm = get_llm_client()
        content_vec = await llm.embed(content[:4000], purpose="query")
        chunk_vec = await llm.embed(chunk_text[:4000], purpose="passage")
        score = _cosine_similarity(content_vec, chunk_vec)
        return GroundednessResult(
            is_grounded=score >= SIMILARITY_THRESHOLD,
            similarity_score=score,
            reason="embedding 유사도 fallback",
            confidence=score,
        )
    except Exception:
        logger.exception("groundedness similarity fallback 실패")
        return GroundednessResult(
            is_grounded=False,
            similarity_score=0.0,
            reason="유사도 계산 실패",
            confidence=0.0,
        )


async def verify_concept_chunks(
    concept_id: str,
    concept_title: str,
    chunk_ids: list[str],
    document_id: str,
) -> GroundednessResult:
    """concept title RAG 검색 결과와 skeleton chunk_ids 일치·유사도 검증."""
    if not chunk_ids:
        return GroundednessResult(
            is_grounded=False,
            similarity_score=0.0,
            reason="chunk_ids 없음",
            unmatched_chunk_ids=[],
        )

    expected = {str(cid) for cid in chunk_ids}
    hits = await search_similar_chunks(
        query=concept_title,
        document_id=document_id,
        concept_id=concept_id,
        top_k=max(len(expected), 3),
    )

    if not hits:
        return GroundednessResult(
            is_grounded=False,
            similarity_score=0.0,
            reason="RAG 검색 결과 없음",
            unmatched_chunk_ids=list(expected),
        )

    hit_ids = {str(h.chunk_id) for h in hits}
    unmatched = sorted(expected - hit_ids)
    avg_sim = sum(h.similarity_score for h in hits) / len(hits)

    is_grounded = avg_sim >= SIMILARITY_THRESHOLD and not unmatched

    if len(expected) == 1 and not is_grounded and not unmatched:
        single_id = next(iter(expected))
        single_hits = [h for h in hits if str(h.chunk_id) == single_id]
        keyword_ok = any(
            _title_keyword_match(concept_title, h.text) for h in single_hits
        )
        if keyword_ok and avg_sim >= SIMILARITY_THRESHOLD * 0.85:
            is_grounded = True

    return GroundednessResult(
        is_grounded=is_grounded,
        similarity_score=avg_sim,
        reason=None if is_grounded else f"평균 유사도 {avg_sim:.2f} 또는 chunk 불일치",
        confidence=avg_sim,
        unmatched_chunk_ids=unmatched,
    )


async def verify_generated_content(content: str, chunks: list) -> GroundednessResult:
    """Solar 또는 embedding fallback으로 생성 텍스트 groundedness 검증."""
    if not content.strip():
        return GroundednessResult(
            is_grounded=False,
            reason="빈 콘텐츠",
            confidence=0.0,
        )

    chunk_text = _chunks_to_text(chunks)
    prompt = f"""다음 학습 콘텐츠가 아래 원문에 근거하는지 판단하세요.

[학습 콘텐츠]
{content[:4000]}

[원문 청크]
{chunk_text[:6000]}

JSON으로만 응답:
{{"is_grounded": true/false, "reason": "한 줄 이유", "confidence": 0.0~1.0}}"""

    try:
        llm = get_llm_client()
        raw = await llm.generate(prompt, json_mode=True)
        data = _parse_json(raw)
        is_grounded = bool(data.get("is_grounded"))
        confidence = float(data.get("confidence") or 0.0)
        reason = str(data.get("reason") or "").strip() or None
        return GroundednessResult(
            is_grounded=is_grounded,
            reason=reason,
            confidence=confidence,
            similarity_score=confidence,
        )
    except Exception:
        logger.exception("Solar groundedness 검증 실패, similarity fallback")
        return await _similarity_fallback(content, chunks)
