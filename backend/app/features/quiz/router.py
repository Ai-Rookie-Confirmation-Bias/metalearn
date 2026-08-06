"""[1.Controller] 문제 페이지 API (docs/QUIZ.md §2-⑧).

풀이 경로(요약·세션·채점)는 LLM 호출 0 — DB 조회만.

생성은 두 문이 있다.
  · `/quiz/generate`               파싱 결과 JSON을 **요청 바디로** 받는다
  · `/quiz/from-parsing/{doc_id}`  파싱 DB에서 **서버가 직접** 읽어 온다
앞의 것은 파싱이 붙기 전에 쓰던 문이고, 지금 정상 경로는 뒤쪽이다.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.llm.exaone import exaone_client
from app.core.llm.solar import solar_client
from app.features.quiz import bridge
from app.features.quiz.schemas import (
    AttemptRequest,
    AttemptResponse,
    ParsedDocument,
    QuizBankSummary,
    SessionRequest,
    SessionResponse,
)
from app.features.quiz.service import QuizService


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


@router.post(
    "/courses/{course_id}/quiz/from-parsing/{document_id}",
    response_model=GenerateBankResponse,
)
async def generate_bank_from_parsing(
    course_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    budget: int | None = Query(
        None, ge=1, le=200, description="목차당 문항 예산. 안 주면 기본 배분"
    ),
) -> GenerateBankResponse:
    """파싱이 끝난 문서로 문제은행을 만든다.

    ⚠️ **읽기 요청에 딸려 돌게 하지 않는다.** 커리큘럼은 목록을 열 때 자동
       주입하지만(싼 변환), 문항 생성은 조각마다 LLM을 여러 번 부른다.
       업로드·재파싱이 끝난 뒤 명시적으로 부르는 문이다.

    같은 문서를 다시 부르면 그 문서의 기존 문항을 **교체**한다.
    """
    from app.features.quiz.schemas import QuizGenConfig

    config = QuizGenConfig(toc_min=budget, toc_max=budget) if budget else None
    try:
        result = await bridge.generate_from_parsing(
            db,
            solar_client,
            course_id,
            document_id,
            verify_llm=_verify_llm(),
            config=config,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not result.report.ok:
        # 파싱 산출물이 계약을 어긴 것이라 사유를 그대로 돌려준다 —
        # 파싱 쪽에 되돌릴 수 있는 형태여야 한다.
        raise HTTPException(status_code=422, detail=result.report.errors)
    return GenerateBankResponse(
        saved=result.saved,
        discarded=result.discarded,
        report_errors=result.report.errors,
        report_warnings=result.report.warnings,
    )


@router.get("/courses/{course_id}/quiz", response_model=list[QuizBankSummary])
def bank_summary(course_id: uuid.UUID, db: Session = Depends(get_db)) -> list[QuizBankSummary]:
    return QuizService(db, solar_client).bank_summary(course_id)


@router.post("/courses/{course_id}/quiz/session", response_model=SessionResponse)
def start_session(
    course_id: uuid.UUID, req: SessionRequest, db: Session = Depends(get_db)
) -> SessionResponse:
    return QuizService(db, solar_client).start_session(
        course_id, uuid.UUID(req.document_id), req.toc_indexes, req.count
    )


@router.post("/quiz/attempts", response_model=AttemptResponse)
def submit_attempt(req: AttemptRequest, db: Session = Depends(get_db)) -> AttemptResponse:
    resp = QuizService(db, solar_client).submit_attempt(
        uuid.UUID(req.quiz_item_id), req.user_input
    )
    if resp is None:
        raise HTTPException(status_code=404, detail="quiz item not found")
    return resp
