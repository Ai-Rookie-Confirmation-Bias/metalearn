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
from app.features.parsing.models import UserDocument
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


def sync_ready_documents(
    db: Session, *, user_id: uuid.UUID | None = None
) -> list[str]:
    """ready인 파싱 문서를 store에 올리고, **그 id 목록**을 돌려준다.

    `user_id`를 주면 그 사람이 소유한 것만 본다(user_documents 조인).
    문서 자체는 공용이지만 책장은 사람 것이다 — 남이 올린 교재가 내 책장에
    뜨면 그건 책장이 아니라 서버 목록이다.

    목록 API가 호출할 때마다 돌린다 — 문서 수가 데모 규모일 때만 싼 경로다.
    이미 올라와 있으면 다시 안 읽는다(재파싱 반영은 `from-parsing?refresh=true`).
    """
    stmt = select(ParsingDocument).where(
        ParsingDocument.status == DocStatus.READY.value
    )
    if user_id is not None:
        stmt = stmt.join(
            UserDocument, UserDocument.document_id == ParsingDocument.id
        ).where(UserDocument.user_id == user_id)

    ids: list[str] = []
    for row in db.scalars(stmt).all():
        key = str(row.id)
        if key in store.documents:
            ids.append(key)
            continue
        try:
            ingest_parsing_document(db, row.id)
            ids.append(key)
        except LookupError as e:
            print(f"[curriculum] 파싱 문서 주입 건너뜀 {key}: {e}")
        except Exception as e:  # noqa: BLE001 — 목록이 죽으면 안 된다
            print(f"[curriculum] 파싱 문서 주입 실패 {key}: {type(e).__name__}: {e}")
    return ids
