"""[1.Controller] 문제 페이지 API (docs/QUIZ.md §2-⑧).

풀이 경로(요약·세션·채점)는 LLM 호출 0 — DB 조회만.

생성은 두 문이 있다.
  · `/quiz/generate`               파싱 결과 JSON을 **요청 바디로** 받는다 (동기, 구경로)
  · `/quiz/from-parsing/{doc_id}`  파싱 DB에서 서버가 직접 읽는다 (**202 접수 + 폴링**)
앞의 것은 파싱이 붙기 전에 쓰던 문이고, 지금 정상 경로는 뒤쪽이다.
"""
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.deps import get_current_user_id
from app.core.llm.exaone import exaone_client
from app.core.llm.solar import solar_client
from app.features.quiz import bridge, jobs
from app.features.quiz.schemas import (
    AttemptRequest,
    AttemptResponse,
    ParsedDocument,
    QuizBankSummary,
    SessionRequest,
    SessionResponse,
)
from app.features.quiz.service import QuizService

logger = logging.getLogger("uvicorn.error")


def _verify_llm():
    """EXAONE 키가 설정돼 있으면 교차 검증 모델로 사용, 없으면 Solar 단일."""
    return exaone_client if settings.EXAONE_API_KEY else None


router = APIRouter()


class GenerateBankRequest(BaseModel):
    document_id: uuid.UUID
    parsed: ParsedDocument
    exam_frequency: dict[str, int] | None = None  # 기출 프로파일 (있을 때만)
    stem_patterns: list[str] | None = None


class GenerateBankResponse(BaseModel):
    saved: int
    discarded: list[str]
    report_errors: list[str]
    report_warnings: list[str]


@router.post("/courses/{course_id}/quiz/generate", response_model=GenerateBankResponse)
async def generate_bank(
    course_id: uuid.UUID, req: GenerateBankRequest, db: Session = Depends(get_db)
) -> GenerateBankResponse:
    service = QuizService(db, solar_client, verify_llm=_verify_llm())
    result = await service.generate_bank(
        course_id,
        req.document_id,
        req.parsed,
        exam_frequency=req.exam_frequency,
        stem_patterns=req.stem_patterns,
    )
    if not result.report.ok:
        raise HTTPException(status_code=422, detail=result.report.errors)
    return GenerateBankResponse(
        saved=result.saved,
        discarded=result.discarded,
        report_errors=result.report.errors,
        report_warnings=result.report.warnings,
    )


class GenStatusResponse(BaseModel):
    """생성 작업 상태 — 파싱의 DocStatus 폴링과 같은 사용법."""

    status: str  # idle | running | done | failed
    saved: int = 0
    discarded: list[str] = []
    report_errors: list[str] = []
    report_warnings: list[str] = []
    error: str | None = None


async def _run_generation(
    course_id: uuid.UUID, document_id: uuid.UUID, config, append: bool = False
) -> None:
    """백그라운드 생성 본체. 요청 세션은 응답과 함께 닫히므로 새 세션을 연다."""
    db = SessionLocal()
    try:
        result = await bridge.generate_from_parsing(
            db,
            solar_client,
            course_id,
            document_id,
            verify_llm=_verify_llm(),
            config=config,
            append=append,
        )
        if not result.report.ok:
            jobs.fail(course_id, document_id, "파싱 산출물 계약 위반: " + " / ".join(result.report.errors))
            return
        jobs.finish(
            course_id,
            document_id,
            saved=result.saved,
            discarded=result.discarded,
            report_errors=result.report.errors,
            report_warnings=result.report.warnings,
        )
    except Exception as exc:  # noqa: BLE001 — 폴링으로 전달할 최종 방어선
        logger.exception("문제은행 생성 실패: course=%s doc=%s", course_id, document_id)
        jobs.fail(course_id, document_id, str(exc))
    finally:
        db.close()


@router.post(
    "/courses/{course_id}/quiz/from-parsing/{document_id}",
    status_code=202,
    response_model=GenStatusResponse,
)
async def generate_bank_from_parsing(
    course_id: uuid.UUID,
    document_id: uuid.UUID,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    budget: int | None = Query(
        None, ge=1, le=200, description="목차당 문항 예산. 안 주면 기본 배분"
    ),
    mode: str = Query(
        "replace",
        pattern="^(replace|append)$",
        description="replace=기존 은행 교체(기본) / append=리필 — 기존 유지 + 새 문항 추가",
    ),
) -> GenStatusResponse:
    """파싱이 끝난 문서로 문제은행 생성을 **접수**한다 (202).

    생성은 분 단위 작업이라(실데이터 실측 888초) 동기로 붙잡으면 타임아웃이
    난다. 접수 즉시 돌아오고, 진행 상태는 같은 경로의 GET `/status`로 폴링한다
    — 업로드→파싱의 202+폴링과 같은 사용법.

    같은 문서를 다시 부르면 그 문서의 기존 문항을 **교체**한다.
    `mode=append`는 리필 — 문제를 다 푼 사용자를 위해 기존 은행을 유지한 채
    새 문항만 추가한다 (기존과 발문이 겹치는 문항은 자동 폐기).
    이미 생성 중이면 409.
    """
    from app.features.quiz.schemas import QuizGenConfig

    # 파싱이 안 끝난 문서는 접수 시점에 걸러 404를 즉시 준다
    try:
        bridge.parsed_document_of(db, document_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # 기출(kind=exam)은 문제은행 재료가 아니다 — 스타일 프로파일로만 쓰인다
    from app.features.parsing.models import Document

    doc = db.get(Document, document_id)
    if doc is not None and doc.kind == "exam":
        raise HTTPException(
            status_code=422,
            detail="기출 자료는 문제은행을 만들지 않습니다 (스타일 참고 전용)",
        )

    if jobs.start(course_id, document_id) is None:
        raise HTTPException(status_code=409, detail="이미 생성 작업이 진행 중입니다")

    config = QuizGenConfig(toc_min=budget, toc_max=budget) if budget else None
    background.add_task(
        _run_generation, course_id, document_id, config, mode == "append"
    )
    return GenStatusResponse(status="running")


@router.get(
    "/courses/{course_id}/quiz/from-parsing/{document_id}/status",
    response_model=GenStatusResponse,
)
def generation_status(course_id: uuid.UUID, document_id: uuid.UUID) -> GenStatusResponse:
    """생성 작업 상태 폴링. 접수 이력이 없으면 idle."""
    job = jobs.get(course_id, document_id)
    if job is None:
        return GenStatusResponse(status="idle")
    return GenStatusResponse(
        status=job.status,
        saved=job.saved,
        discarded=job.discarded,
        report_errors=job.report_errors,
        report_warnings=job.report_warnings,
        error=job.error,
    )


@router.get("/courses/{course_id}/quiz", response_model=list[QuizBankSummary])
def bank_summary(
    course_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[QuizBankSummary]:
    # user_id는 "학습함" 라벨(사용자별 진도)에만 쓰인다 — 문항 자체는 공용
    return QuizService(db, solar_client).bank_summary(course_id, user_id=user_id)


@router.post("/courses/{course_id}/quiz/session", response_model=SessionResponse)
def start_session(
    course_id: uuid.UUID, req: SessionRequest, db: Session = Depends(get_db)
) -> SessionResponse:
    # exclude_ids는 클라이언트 localStorage 출신 — 손상된 값 하나 때문에
    # 세션 전체를 거부하지 않는다 (파싱 안 되는 id는 그냥 무시).
    exclude: list[uuid.UUID] = []
    for raw in req.exclude_ids:
        try:
            exclude.append(uuid.UUID(raw))
        except ValueError:
            continue
    return QuizService(db, solar_client).start_session(
        course_id, uuid.UUID(req.document_id), req.toc_indexes, req.count, exclude
    )


@router.post("/quiz/attempts", response_model=AttemptResponse)
def submit_attempt(req: AttemptRequest, db: Session = Depends(get_db)) -> AttemptResponse:
    resp = QuizService(db, solar_client).submit_attempt(
        uuid.UUID(req.quiz_item_id), req.user_input
    )
    if resp is None:
        raise HTTPException(status_code=404, detail="quiz item not found")
    return resp
