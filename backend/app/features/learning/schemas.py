"""[2.DTO] Pydantic 입출력 타입 및 유효성 검증."""
from pydantic import BaseModel


class GenerateRequest(BaseModel):
    topic: str


class GenerateResponse(BaseModel):
    content: str
