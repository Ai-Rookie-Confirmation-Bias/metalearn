"""pgvector 기반 유사 chunk 검색."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.llm.factory import get_llm_client
from app.core.memory_store import get_memory_store
from app.features.materials.models import DocumentChunk

logger = logging.getLogger(__name__)

_async_engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(_async_engine, expire_on_commit=False)


@dataclass
class ChunkResult:
    chunk_id: uuid.UUID
    page_number: int
    text: str
    similarity_score: float
    concept_id: str | None = None


async def search_similar_chunks(
    query: str,
    document_id: str,
    top_k: int = 5,
    concept_id: str | None = None,
    *,
    session: AsyncSession | None = None,
) -> list[ChunkResult]:
    if not query.strip():
        return []

    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        logger.warning("search_similar_chunks: invalid document_id=%s", document_id)
        return []

    if not settings.PERSIST_TO_DB:
        return await _search_memory_chunks(doc_uuid, query, top_k, concept_id)

    async def _run(db: AsyncSession) -> list[ChunkResult]:
        llm = get_llm_client()
        query_vec = await llm.embed(query, purpose="query")

        distance_expr = DocumentChunk.embedding.cosine_distance(query_vec)
        similarity_expr = (1 - distance_expr).label("similarity_score")

        stmt = (
            select(
                DocumentChunk.id,
                DocumentChunk.page_number,
                DocumentChunk.content,
                DocumentChunk.concept_id,
                similarity_expr,
            )
            .where(DocumentChunk.document_id == doc_uuid)
            .where(DocumentChunk.embedding.isnot(None))
        )

        if concept_id is not None:
            stmt = stmt.where(DocumentChunk.concept_id == concept_id)

        stmt = stmt.order_by(distance_expr).limit(top_k)
        rows = (await db.execute(stmt)).all()
        return [
            ChunkResult(
                chunk_id=row.id,
                page_number=row.page_number,
                text=row.content,
                similarity_score=float(row.similarity_score),
                concept_id=row.concept_id,
            )
            for row in rows
        ]

    try:
        if session is not None:
            return await _run(session)
        async with AsyncSessionLocal() as db:
            return await _run(db)
    except Exception:
        logger.exception(
            "search_similar_chunks 실패 document_id=%s concept_id=%s",
            document_id,
            concept_id,
        )
        return []


async def _search_memory_chunks(
    document_id: uuid.UUID,
    query: str,
    top_k: int,
    concept_id: str | None,
) -> list[ChunkResult]:
    mem = get_memory_store()
    try:
        llm = get_llm_client()
        query_vec = await llm.embed(query, purpose="query")
    except Exception:
        logger.exception("memory RAG embed 실패")
        return []

    rows = mem.search_chunks(document_id, query_vec, top_k, concept_id)
    return [
        ChunkResult(
            chunk_id=chunk.id,
            page_number=chunk.page_number,
            text=chunk.content,
            similarity_score=score,
            concept_id=chunk.concept_id,
        )
        for chunk, score in rows
    ]
