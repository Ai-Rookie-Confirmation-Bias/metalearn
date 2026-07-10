"""인증 응답 스키마."""
import uuid

from pydantic import BaseModel


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None = None
    provider: str

    model_config = {"from_attributes": True}
