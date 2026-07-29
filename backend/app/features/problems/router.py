"""[1.Controller] 문제 생성 에이전트 엔드포인트.

curl/Postman으로 직접 호출해 문항 JSON 품질을 반복 확인한다(프론트 조립 X).
"""
from fastapi import APIRouter

from app.features.problems.schemas import (
    GenerateProblemsRequest,
    GenerateProblemsResponse,
)
from app.features.problems.service import ProblemGeneratorService

router = APIRouter()


@router.post("/generate", response_model=GenerateProblemsResponse)
async def generate_problems(
    req: GenerateProblemsRequest,
) -> GenerateProblemsResponse:
    return await ProblemGeneratorService().generate(req)
