"""[3.Service] PDF 업로드·파싱·skeleton 생성."""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.document_intelligence.factory import get_document_intelligence
from app.core.document_parse.factory import get_document_parser
from app.core.groundedness import log_concept_groundedness, verify_concept_chunks
from app.core.llm.factory import get_llm_client
from app.features.materials.chunk_builder import tag_concept_chunks
from app.features.materials.repository import MaterialsRepository
from app.features.materials.schemas import DocumentResponse, DocumentSkeleton

logger = logging.getLogger(__name__)


class MaterialsService:
    def __init__(self, db: Session) -> None:
        self.repo = MaterialsRepository(db)
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def upload_and_parse(self, file: UploadFile) -> DocumentResponse:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다.")

        doc = self.repo.create_document(filename=file.filename, storage_path="")
        dest = self.upload_dir / f"{doc.id}.pdf"

        content = await file.read()
        dest.write_bytes(content)
        self.repo.update_document(doc, storage_path=str(dest))

        try:
            parser = get_document_parser()
            parsed = await parser.parse_pdf(dest)
            pages = parsed.pages
            page_to_chunk_id: dict[int, str] = {}
            llm = get_llm_client()

            for page_num, text in pages:
                embedding = (
                    await llm.embed(text, purpose="passage") if text else None
                )
                chunk = self.repo.add_chunk(doc.id, page_num, text, embedding)
                page_to_chunk_id[page_num] = str(chunk.id)

            intelligence = get_document_intelligence()
            skeleton, sk_mode, sk_note = await intelligence.build_skeleton_with_meta(
                doc.id, pages, page_to_chunk_id
            )

            skeleton = tag_concept_chunks(self.repo, doc.id, skeleton)

            for concept in skeleton.concepts:
                if not concept.chunk_ids:
                    continue
                result = await verify_concept_chunks(
                    concept_id=concept.id,
                    concept_title=concept.title,
                    chunk_ids=concept.chunk_ids,
                    document_id=str(doc.id),
                )
                log_concept_groundedness(concept.id, result)

            self.repo.update_document(
                doc,
                page_count=skeleton.page_count,
                parse_status="parsed",
                skeleton={
                    **skeleton.model_dump(mode="json"),
                    "_parse_engine": parsed.engine,
                    "_parse_note": parsed.note,
                    "_parse_mode": sk_mode,
                    "_skeleton_note": sk_note,
                },
            )
        except Exception as exc:
            self.repo.update_document(doc, parse_status="failed")
            raise HTTPException(status_code=422, detail=f"PDF 파싱 실패: {exc}") from exc

        refreshed = self.repo.get_document(doc.id)
        assert refreshed is not None
        resp = DocumentResponse.model_validate(refreshed)
        sk = refreshed.skeleton or {}
        return resp.model_copy(
            update={
                "parse_engine": sk.get("_parse_engine", "pypdf"),
                "parse_mode": sk.get("_parse_mode", "local"),
            }
        )

    def get_document(self, document_id: uuid.UUID) -> DocumentResponse:
        doc = self.repo.get_document(document_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
        return DocumentResponse.model_validate(doc)

    def get_skeleton(self, document_id: uuid.UUID) -> DocumentSkeleton:
        doc = self.repo.get_document(document_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
        if doc.parse_status != "parsed" or not doc.skeleton:
            raise HTTPException(status_code=409, detail="문서 파싱이 완료되지 않았습니다.")
        clean = {k: v for k, v in doc.skeleton.items() if not str(k).startswith("_")}
        return DocumentSkeleton.model_validate(clean)
