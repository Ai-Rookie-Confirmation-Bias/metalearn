"""FastAPI 진입점: 인스턴스 생성, CORS/미들웨어 등록, 라우터 통합."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.config import settings

app = FastAPI(title="MetaLearn API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.on_event("startup")
def _load_curriculum() -> None:
    """파싱 md를 읽어 커리큘럼을 메모리에 올린다.

    DB가 붙기 전까지의 임시 경로다(로드맵 STEP 3). 파싱 팀과 통합하면 업로드로
    바뀐다. fixture가 없어도 서버는 떠야 하므로 실패를 삼킨다.
    """
    from app.features.curriculum.store import store

    try:
        loaded = store.load_fixtures()
        print(f"[curriculum] 자료 {len(loaded)}개 로드: {', '.join(loaded)}")
    except Exception as e:  # noqa: BLE001
        print(f"[curriculum] 로드 실패(무시하고 계속): {type(e).__name__}: {e}")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
