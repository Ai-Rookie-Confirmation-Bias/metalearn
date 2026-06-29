"""[4.Repository] 문서·청크 DB 접근."""
import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.memory_store import get_memory_store
from app.features.materials.models import Document, DocumentChunk


class MaterialsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._mem = get_memory_store()

    def create_document(self, filename: str, storage_path: str) -> Document:
        if not settings.PERSIST_TO_DB:
            return self._mem.create_document(filename, storage_path)
        doc = Document(filename=filename, storage_path=storage_path)
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def get_document(self, document_id: uuid.UUID) -> Document | None:
        if not settings.PERSIST_TO_DB:
            return self._mem.get_document(document_id)
        return self.db.get(Document, document_id)

    def update_document(
        self,
        doc: Document,
        *,
        storage_path: str | None = None,
        page_count: int | None = None,
        parse_status: str | None = None,
        skeleton: dict | None = None,
    ) -> Document:
        if not settings.PERSIST_TO_DB:
            return self._mem.update_document(
                doc,
                storage_path=storage_path,
                page_count=page_count,
                parse_status=parse_status,
                skeleton=skeleton,
            )
        if storage_path is not None:
            doc.storage_path = storage_path
        if page_count is not None:
            doc.page_count = page_count
        if parse_status is not None:
            doc.parse_status = parse_status
        if skeleton is not None:
            doc.skeleton = skeleton
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def delete_chunks_for_document(self, document_id: uuid.UUID) -> None:
        if not settings.PERSIST_TO_DB:
            self._mem.delete_chunks_for_document(document_id)
            return
        self.db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        self.db.commit()

    def add_chunk(
        self,
        document_id: uuid.UUID,
        page_number: int,
        content: str,
        embedding: list[float] | None = None,
        *,
        concept_id: str | None = None,
    ) -> DocumentChunk:
        if not settings.PERSIST_TO_DB:
            return self._mem.add_chunk(
                document_id, page_number, content, embedding, concept_id=concept_id
            )
        chunk = DocumentChunk(
            document_id=document_id,
            page_number=page_number,
            concept_id=concept_id,
            content=content,
            embedding=embedding,
        )
        self.db.add(chunk)
        self.db.commit()
        self.db.refresh(chunk)
        return chunk

    def tag_chunk_concept(self, chunk: DocumentChunk, concept_id: str) -> bool:
        """concept_id가 비어 있을 때만 태깅. 이미 태깅된 페이지는 False."""
        if chunk.concept_id is not None:
            return False
        if not settings.PERSIST_TO_DB:
            return self._mem.tag_chunk_concept(chunk, concept_id)
        chunk.concept_id = concept_id
        self.db.commit()
        self.db.refresh(chunk)
        return True

    def get_chunk_by_page(
        self, document_id: uuid.UUID, page_number: int
    ) -> DocumentChunk | None:
        if not settings.PERSIST_TO_DB:
            return self._mem.get_chunk_by_page(document_id, page_number)
        stmt = (
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.page_number == page_number,
            )
            .limit(1)
        )
        return self.db.scalars(stmt).first()

    def list_chunks(self, document_id: uuid.UUID) -> list[DocumentChunk]:
        if not settings.PERSIST_TO_DB:
            return self._mem.list_chunks(document_id)
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.page_number)
        )
        return list(self.db.scalars(stmt))
