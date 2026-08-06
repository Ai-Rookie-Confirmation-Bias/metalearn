"""파싱 DocumentTree → 커리큘럼 store.

어댑터(`document_from_tree`)는 순수 변환만 한다. 여기는 **언제·무엇을** 올리는지.
책장 목록을 열 때 ready 문서를 끌어오고, 명시 import도 같은 문을 지난다.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.parsing.models import DocStatus
from app.features.parsing.models import Document as ParsingDocument
from app.features.parsing.service import ParsingService

from .models import Document
from .store import store


def ingest_parsing_document(
    db: Session,
    document_id: uuid.UUID,
    *,
    refresh: bool = False,
) -> Document:
    """파싱 ready 문서 하나 → 학습 store.

    `doc_id`는 파싱 UUID 문자열. 책장 링크 `/curriculum/{id}`가 그 값으로 열린다.
    """
    key = str(document_id)
    if not refresh and key in store.documents:
        return store.documents[key]

    try:
        tree = ParsingService(db).get_tree(document_id)
    except ValueError as exc:
        raise LookupError(str(exc)) from exc

    meta = tree.document
    if meta.status != DocStatus.READY.value:
        raise LookupError(
            f"아직 파싱이 끝나지 않았습니다: {document_id} (status={meta.status})"
        )

    return store.ingest_tree(tree.model_dump(mode="json"), doc_id=key)


def sync_ready_documents(db: Session) -> list[str]:
    """DB에 ready인 파싱 문서 중 store에 없는 것을 올린다.

    목록 API가 호출할 때마다 돌린다 — 문서 수가 데모 규모일 때만 싼 경로다.
    이미 올린 것은 건너뛴다(재파싱 반영은 `from-parsing?refresh=true`).
    """
    rows = db.scalars(
        select(ParsingDocument).where(ParsingDocument.status == DocStatus.READY.value)
    ).all()
    added: list[str] = []
    for row in rows:
        key = str(row.id)
        if key in store.documents:
            continue
        try:
            ingest_parsing_document(db, row.id)
            added.append(key)
        except LookupError as e:
            print(f"[curriculum] 파싱 문서 주입 건너뜀 {key}: {e}")
        except Exception as e:  # noqa: BLE001 — 목록이 죽으면 안 된다
            print(f"[curriculum] 파싱 문서 주입 실패 {key}: {type(e).__name__}: {e}")
    return added
