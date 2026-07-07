"""FastAPI 진입점: 인스턴스 생성, CORS/미들웨어 등록, 라우터 통합."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models_registry  # noqa: F401  (모든 ORM 모델 등록 — FK 해석용)
from app.api import api_router
from app.core.config import settings
from app.core.llm.solar import solar_client


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await solar_client.aclose()  # 공유 커넥션 풀 정리(미생성이면 no-op)


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
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "persist_to_db": settings.PERSIST_TO_DB,
        "storage": "postgresql" if settings.PERSIST_TO_DB else "memory",
        "llm_provider": settings.llm_provider,
        "llm_model": settings.SOLAR_MODEL if settings.llm_provider == "solar" else "mock",
    }
