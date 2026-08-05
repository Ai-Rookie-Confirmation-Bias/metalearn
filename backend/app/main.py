"""FastAPI 진입점: 인스턴스 생성, CORS/미들웨어 등록, 라우터 통합."""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models_registry  # noqa: F401 — 전 모델 로드 (FK 해석)
from app.api import api_router
from app.core.config import settings
from app.core.llm.solar import solar_client


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    yield
    # Solar 공유 커넥션 풀 정리
    await solar_client.aclose()


app = FastAPI(title="MetaLearn API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
