"""파싱 라우터.

  POST /parsing/documents            업로드 → 백그라운드 파싱 시작
  GET  /parsing/documents/{id}       상태 조회 (프론트가 폴링)
  GET  /parsing/documents/{id}/tree  목차 + 조각 + 개념
"""
from __future__ import annotations

import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.deps import get_current_user_id
from app.features.parsing.models import DocFigure, MaterialRole
from app.features.parsing.schemas import ConceptHitOut, DocumentOut, DocumentTree
from app.features.parsing.service import ParsingService

router = APIRouter()


async def _run_pipeline(document_id: uuid.UUID, file_bytes: bytes) -> None:
    """백그라운드 실행. 요청 세션은 이미 닫혔으므로 세션을 새로 연다."""
    db = SessionLocal()
    try:
        await ParsingService(db).run(document_id, file_bytes)
    except Exception:  # noqa: BLE001 — 실패 사유는 service가 문서에 기록한다
        pass
    finally:
        db.close()


@router.post("/documents", response_model=DocumentOut, status_code=202)
async def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    role: str = MaterialRole.SKELETON.value,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> DocumentOut:
    """자료 업로드. 파싱은 백그라운드로 돌고 상태는 폴링으로 확인한다.

    같은 파일(지문 일치)이 이미 파싱돼 있으면 그대로 재사용한다 —
    문서가 공용이라 가능한 일이다. 그래도 **소유는 사람마다 따로 남는다**
    (user_documents). 그래서 남이 올려둔 책을 내가 올리면 파싱은 0초인데
    내 책장에는 새로 꽂힌다.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")

    # **파싱을 시작하기 전에 막는다.** 실측: 113MB PDF가 업스테이지에서 413으로
    # 죽었는데, 그때까지 파일을 다 올리고 파이프라인을 띄운 뒤였다. 화면에는
    # 영어 HTTP 에러가 그대로 떴고 기다린 시간은 통째로 헛일이었다.
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(file_bytes) > limit:
        raise HTTPException(
            status_code=413,
            detail=(
                f"파일이 너무 큽니다 ({len(file_bytes) / 1024 / 1024:.0f}MB). "
                f"{settings.MAX_UPLOAD_MB}MB 이하로 올려 주세요."
            ),
        )

    service = ParsingService(db)
    document_id, needs_parse = service.register(
        file_bytes=file_bytes,
        filename=file.filename or "document.pdf",
        user_id=user_id,
        role=role,
    )
    if needs_parse:
        background.add_task(_run_pipeline, document_id, file_bytes)

    document = service.repo.get_document(document_id)
    return DocumentOut.model_validate(document)


DOCUMENT_KINDS = {"textbook", "slide", "notes", "exam"}


class DocumentKindIn(BaseModel):
    kind: str


@router.patch("/documents/{document_id}/kind", response_model=DocumentOut)
def set_document_kind(
    document_id: uuid.UUID,
    body: DocumentKindIn,
    db: Session = Depends(get_db),
) -> DocumentOut:
    """위저드의 자료 유형 선택(교재/슬라이드/필기/기출)을 저장한다.

    지금까지 이 선택은 프론트 상태에만 있고 서버로 오지 않았다 — 기출(exam)
    구분이 서버에 없으면 기출 제외·스타일 프로파일(QUIZ.md §2-③)이 성립하지
    않는다. 드롭다운을 바꿀 때마다 호출된다 (업로드는 파일 추가 즉시 시작되어
    업로드 시점엔 유형이 미확정이라 별도 문으로 받는다).
    """
    if body.kind not in DOCUMENT_KINDS:
        raise HTTPException(
            status_code=422, detail=f"kind는 {sorted(DOCUMENT_KINDS)} 중 하나"
        )
    document = ParsingService(db).repo.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="문서가 없습니다.")
    document.kind = body.kind
    db.commit()
    return DocumentOut.model_validate(document)


@router.get("/concepts/search", response_model=list[ConceptHitOut])
async def search_concepts(
    q: str = Query(..., min_length=1, description="찾을 개념 이름이나 설명"),
    limit: int = Query(10, ge=1, le=50),
    min_sim: float = Query(0.0, ge=0.0, le=1.0),
    document_id: list[uuid.UUID] | None = Query(None),
    db: Session = Depends(get_db),
) -> list[ConceptHitOut]:
    """개념을 뜻으로 찾는다. **문서 경계를 넘는다.**

    이름이 안 겹쳐도 찾는다 — "소프트웨어 비용 산정"으로 검색하면 이름에 그
    말이 없는 "COCOMO 모형"이 올라온다. 자료 간 개념 매칭과 외부 조달이
    이 위에 올라간다.

    document_id를 여러 번 주면 그 자료들 안에서만 찾는다.
    """
    return await ParsingService(db).search_concepts(
        q, limit=limit, document_ids=document_id, min_sim=min_sim
    )


@router.get("/figures/{figure_id}")
def get_figure(figure_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    """그림 원본 이미지.

    **debug 라우터에도 같은 게 있지만 그쪽은 배포에서 빠진다.** 학습 화면이
    교재 그림을 보여주려면 정식 경로가 필요해서 여기 뒀다.

    문서 id를 안 받는다 — 그림 id가 UUID라 그것만으로 충분하고, 코스(자료 여럿)
    화면에서는 그림이 어느 문서 것인지 화면이 따로 알 이유가 없다.

    캐시를 길게 준다. 파싱 결과물이라 내용이 바뀌지 않고, 한 화면에 여러 장이
    붙는다(실측 자료 하나에 23장·1.6MB).
    """
    figure = db.get(DocFigure, figure_id)
    if figure is None:
        raise HTTPException(status_code=404, detail="그림을 찾을 수 없습니다.")
    return Response(
        content=figure.data,
        media_type=figure.mime,
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_status(document_id: uuid.UUID, db: Session = Depends(get_db)) -> DocumentOut:
    document = ParsingService(db).repo.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    return DocumentOut.model_validate(document)


@router.get("/documents/{document_id}/tree", response_model=DocumentTree)
def get_tree(document_id: uuid.UUID, db: Session = Depends(get_db)) -> DocumentTree:
    try:
        return ParsingService(db).get_tree(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
