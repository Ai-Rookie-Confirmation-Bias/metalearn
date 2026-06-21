"""[3.Service] 핵심 비즈니스 로직 + LLM 연동."""
from sqlalchemy.orm import Session

from app.core.llm.solar import solar_client
from app.features.learning.repository import LearningRepository
from app.features.learning.schemas import GenerateRequest, GenerateResponse


class LearningService:
    def __init__(self, db: Session) -> None:
        self.repo = LearningRepository(db)

    async def generate(self, req: GenerateRequest) -> GenerateResponse:
        content = await solar_client.generate(f"다음 주제로 학습 항목을 만들어줘: {req.topic}")
        self.repo.add(content=content)
        return GenerateResponse(content=content)
