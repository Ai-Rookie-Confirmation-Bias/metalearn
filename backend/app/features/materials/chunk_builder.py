"""skeleton concept → 페이지 chunk에 concept_id 태깅."""
from __future__ import annotations

import uuid

from app.features.materials.repository import MaterialsRepository
from app.features.materials.schemas import ConceptEntry, DocumentSkeleton


def tag_concept_chunks(
    repo: MaterialsRepository,
    document_id: uuid.UUID,
    skeleton: DocumentSkeleton,
) -> DocumentSkeleton:
    """
    페이지 단위 chunk는 유지하고 concept.page_numbers 기준으로 concept_id 태깅.
    한 페이지가 여러 concept에 걸치면 skeleton 순서상 먼저 나온 concept_id만 적용.
    """
    updated: list[ConceptEntry] = []

    for concept in skeleton.concepts:
        chunk_ids: list[str] = []

        for page_num in concept.page_numbers:
            chunk = repo.get_chunk_by_page(document_id, page_num)
            if chunk is None:
                continue

            chunk_ids.append(str(chunk.id))
            repo.tag_chunk_concept(chunk, concept.id)

        updated.append(concept.model_copy(update={"chunk_ids": chunk_ids}))

    return skeleton.model_copy(update={"concepts": updated})
