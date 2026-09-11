"""6·9단계 — 임베딩.

**비대칭 임베딩**: 조각은 passage 모델, 개념은 query 모델을 쓴다.
개념명("미분")으로 원문 조각을 찾는 게 실제 사용 패턴이라, 양쪽을 같은
모델로 넣으면 검색 품질이 떨어진다.

Solar ⌈조각수/16⌉ + ⌈개념수/64⌉회.
"""
from __future__ import annotations

import logging

from app.core.config import settings
from app.core.llm.solar import solar_client
from app.features.parsing.schemas import Segment

_log = logging.getLogger("uvicorn.error")


async def embed_segments(segments: list[Segment]) -> list[list[float]]:
    """조각 본문 임베딩. 입력은 절단한다 (임베딩 모델 토큰 한계).

    입력 순서대로 반환하므로 zip으로 조각과 짝지어도 안전하다.
    """
    if not segments:
        return []

    texts = [s.content[: settings.SEGMENT_EMBED_MAX_CHARS] for s in segments]
    vectors: list[list[float]] = []
    batch = settings.SEGMENT_EMBED_BATCH
    for i in range(0, len(texts), batch):
        vectors.extend(
            await solar_client.embed_batch(texts[i : i + batch], purpose="passage")
        )

    _log.info("조각 임베딩: %d개 (%d회 호출)", len(vectors), (len(texts) + batch - 1) // batch)
    return vectors


async def embed_texts(texts: list[str]) -> dict[str, list[float]]:
    """개념 텍스트 배치 임베딩 → {텍스트: 벡터}.

    같은 텍스트가 여러 번 들어와도 한 번만 부른다. 캐시로 돌려주는 이유는
    저장 단계가 개념을 만나는 순서와 임베딩 순서가 다르기 때문이다.
    """
    unique = list(dict.fromkeys(t for t in texts if t))
    if not unique:
        return {}

    cache: dict[str, list[float]] = {}
    batch = settings.EMBED_BATCH_SIZE
    for i in range(0, len(unique), batch):
        chunk = unique[i : i + batch]
        cache.update(zip(chunk, await solar_client.embed_batch(chunk, purpose="query")))

    _log.info("개념 임베딩: %d개 (%d회 호출)", len(cache), (len(unique) + batch - 1) // batch)
    return cache
