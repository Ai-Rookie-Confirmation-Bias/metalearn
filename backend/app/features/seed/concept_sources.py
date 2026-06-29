"""concept ↔ chunk 텍스트 매핑."""
from __future__ import annotations

import uuid

from app.features.materials.models import DocumentChunk
from app.features.materials.schemas import ConceptEntry, DocumentSkeleton


class ConceptSource:
    def __init__(
        self,
        concept_id: str,
        text: str,
        page_numbers: list[int],
        chunk_ids: list[uuid.UUID],
        prior_concept_ids: list[str],
    ) -> None:
        self.concept_id = concept_id
        self.text = text
        self.page_numbers = page_numbers
        self.chunk_ids = chunk_ids
        self.prior_concept_ids = prior_concept_ids


def build_concept_sources(
    skeleton: DocumentSkeleton,
    chunks: list[DocumentChunk],
    concepts_in_range: list[str],
) -> dict[str, ConceptSource]:
    chunk_by_concept = {c.concept_id: c for c in chunks if c.concept_id}
    page_to_chunk = {c.page_number: c for c in chunks}
    concept_map = {c.id: c for c in skeleton.concepts}
    sources: dict[str, ConceptSource] = {}

    for concept_id in concepts_in_range:
        entry = concept_map.get(concept_id)
        if entry:
            page_numbers = entry.page_numbers
            prior_ids = entry.prior_concept_ids
        elif concept_id.startswith("c") and concept_id[1:].isdigit():
            page_numbers = [int(concept_id[1:])]
            prior_ids = []
        else:
            continue

        concept_chunk = chunk_by_concept.get(concept_id)
        if concept_chunk and concept_chunk.content.strip():
            sources[concept_id] = ConceptSource(
                concept_id=concept_id,
                text=concept_chunk.content.strip(),
                page_numbers=page_numbers,
                chunk_ids=[concept_chunk.id],
                prior_concept_ids=prior_ids,
            )
            continue

        texts: list[str] = []
        chunk_ids: list[uuid.UUID] = []
        for pn in page_numbers:
            ch = page_to_chunk.get(pn)
            if ch and ch.content.strip():
                texts.append(ch.content.strip())
                chunk_ids.append(ch.id)

        if not texts:
            continue

        sources[concept_id] = ConceptSource(
            concept_id=concept_id,
            text="\n\n".join(texts),
            page_numbers=page_numbers,
            chunk_ids=chunk_ids,
            prior_concept_ids=prior_ids,
        )

    return sources
