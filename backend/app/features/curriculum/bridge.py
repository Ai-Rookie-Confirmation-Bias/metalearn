"""파싱 트리·코스 트리 → 커리큘럼 store.

어댑터는 순수 변환만 한다. 여기는 **언제·무엇을** 올리는지.
책장 목록을 열 때 ready 문서와 코스를 끌어오고, 명시 import도 같은 문을 지난다.

문이 둘이다. 재료가 다를 뿐 결과는 같은 `Document`다:

    자료 하나   ingest_parsing_document   ParsingService.get_tree  → doc_topics
    수업 하나   ingest_course             CourseService.tree       → course_topics
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.course.models import Course, CourseDocument
from app.features.course.service import CourseService
from app.features.course.supply import GENERATED
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
        ParsingDocument.status == DocStatus.READY.value,
        # 26이 만든 보강 자료는 뺀다. 그건 코스 목차에 끼워 쓰는 것이지
        # 책장에서 골라 읽는 책이 아니다 — 원문이 없고 명세만 들었다.
        ParsingDocument.source_format != GENERATED,
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


def sync_public_documents(db: Session) -> list[str]:
    """**기본 제공 자료**를 store에 올리고 그 id 목록을 돌려준다.

    `sync_ready_documents`와 나란하다. 다른 건 소유 조건뿐이다 — 이쪽은
    `visibility='public'`이라 주인이 없고 **누구 책장에나** 뜬다.

    쓰임새가 둘이다:

        책장   "기본 제공 자료" 칸에 놓인다(내가 올린 것과 갈라 보여준다)
        보강   `supply._existing_hits`가 선수 개념을 찾을 때 여기서 걸린다.
               그 조회는 "내 코스 밖 · 실제 교재 · 원문 조각 있음"만 보는데,
               DB에 남의 교재가 없으면 찾을 게 없다(실측 히트율 28개 중 2개).

    26이 만든 보강 자료도 `visibility='public'`이지만 여기 안 들어온다 —
    `source_format=GENERATED`라 아래 조건에서 빠진다. 그건 원문 없는 명세라
    책장에서 골라 읽는 책이 아니다.
    """
    stmt = select(ParsingDocument).where(
        ParsingDocument.status == DocStatus.READY.value,
        ParsingDocument.visibility == "public",
        ParsingDocument.source_format != GENERATED,
    )

    ids: list[str] = []
    for row in db.scalars(stmt).all():
        key = str(row.id)
        store.public_ids.add(key)
        if key in store.documents:
            ids.append(key)
            continue
        try:
            ingest_parsing_document(db, row.id)
            ids.append(key)
        except LookupError as e:
            print(f"[curriculum] 기본 자료 주입 건너뜀 {key}: {e}")
        except Exception as e:  # noqa: BLE001 — 목록이 죽으면 안 된다
            print(f"[curriculum] 기본 자료 주입 실패 {key}: {type(e).__name__}: {e}")
    return ids


async def ingest_course(
    db: Session,
    course_id: uuid.UUID,
    *,
    refresh: bool = False,
) -> Document:
    """코스 하나 → 학습 store.

    `ingest_parsing_document`와 나란하다. 다른 건 재료뿐이고
    (`CourseService.tree`는 뼈대 목차에 본문 자료 설명을 얹어 준다)
    키도 같은 자리를 쓴다 — 코스 id 문자열.

    async인 이유: 자료끼리 개념 연결(18단계)이 아직 없으면 여기서 계산한다.
    문서쌍 단위로 저장되므로 두 번째부터는 DB 조회뿐이다.
    """
    key = str(course_id)
    if not refresh and key in store.documents:
        return store.documents[key]

    tree = await CourseService(db).tree(course_id)
    return store.ingest_course_tree(tree.model_dump(mode="json"), doc_id=key)


def ingest_course_stored(db: Session, course_id: uuid.UUID) -> Document:
    """`ingest_course`의 동기판 — **저장된 연결만** 읽는다.

    동기 자리(딥링크 폴백)에서만 쓴다. 연결을 새로 계산하지 않으므로 본문이
    아직 안 붙었을 수 있고, 그건 다음 `sync_courses`가 채운다.
    """
    key = str(course_id)
    if key in store.documents:
        return store.documents[key]
    if db.get(Course, course_id) is None:
        raise LookupError(f"코스를 찾을 수 없습니다: {course_id}")

    tree = CourseService(db).tree_stored(course_id)
    return store.ingest_course_tree(tree.model_dump(mode="json"), doc_id=key)


def course_member_document_ids(
    db: Session, *, user_id: uuid.UUID | None = None
) -> set[str]:
    """코스에 묶인 자료 id들.

    책장에서 **뺀다.** 안 그러면 PPT 한 권 · 교재 한 권 · 그 둘을 묶은 수업
    한 권이 나란히 떠서, 학습자가 어느 걸 눌러야 하는지 알 수 없다.

    ⚠️ `user_id`를 주면 **그 사람의 코스에 묶인 것만** 뺀다. 자료는 공용이라
    남이 자기 수업에 넣었다는 이유로 내 책장에서 사라지면 안 된다.
    """
    stmt = select(CourseDocument.document_id)
    if user_id is not None:
        stmt = stmt.join(Course, Course.id == CourseDocument.course_id).where(
            Course.user_id == user_id
        )
    return {str(v) for v in db.scalars(stmt)}


async def sync_courses(
    db: Session, *, user_id: uuid.UUID | None = None
) -> list[str]:
    """코스를 store에 올리고 **그 id 목록**을 돌려준다.

    `sync_ready_documents`와 같은 사정이고 같은 이유로 **사람별로 거른다** —
    `courses.user_id`가 있으니 남의 수업이 내 책장에 뜨면 안 된다.
    """
    stmt = select(Course)
    if user_id is not None:
        stmt = stmt.where(Course.user_id == user_id)

    ids: list[str] = []
    for row in db.scalars(stmt).all():
        key = str(row.id)
        if key in store.documents:
            ids.append(key)
            continue
        try:
            await ingest_course(db, row.id)
            ids.append(key)
        except Exception as e:  # noqa: BLE001 — 목록이 죽으면 안 된다
            print(f"[curriculum] 코스 주입 실패 {key}: {type(e).__name__}: {e}")
    return ids
