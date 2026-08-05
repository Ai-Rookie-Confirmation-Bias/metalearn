"""[1.Controller] 문제 페이지 API (docs/QUIZ.md §2-⑧).

풀이 경로(요약·세션·채점)는 LLM 호출 0 — DB 조회만.
생성 트리거는 파싱 완료 시 내부 호출이 정석이나, 파이프라인이 붙기 전까지
파싱 결과 JSON을 직접 받는 엔드포인트로 노출한다 (팀원 계약 = 요청 바디).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.llm.solar import solar_client
from app.features.quiz.schemas import (
    AttemptRequest,
    AttemptResponse,
    ParsedDocument,
    QuizBankSummary,
    SessionRequest,
    SessionResponse,
)
from app.features.quiz.service import QuizService

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
    service = QuizService(db, solar_client)
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
