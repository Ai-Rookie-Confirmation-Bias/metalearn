"""FastAPI 진입점: 인스턴스 생성, CORS/미들웨어 등록, 라우터 통합."""
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.core.config import settings

app = FastAPI(title="MetaLearn API", version="0.1.0")


@app.exception_handler(httpx.HTTPError)
async def httpx_error_handler(request: Request, exc: httpx.HTTPError) -> JSONResponse:
    """Solar 등 외부 AI 호출 실패(타임아웃/네트워크)를 깔끔한 503으로 변환.

    처리되지 않으면 raw 500이 되어 원인 파악이 어렵다.
    """
    kind = type(exc).__name__
    return JSONResponse(
        status_code=503,
        content={"detail": f"AI 서비스 호출 실패({kind}). 잠시 후 다시 시도하세요."},
    )

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
