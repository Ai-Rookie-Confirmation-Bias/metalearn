"""FastAPI 진입점: 인스턴스 생성, CORS/미들웨어 등록, 라우터 통합."""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models_registry  # noqa: F401 — 전 모델 로드 (FK 해석)
from app.api import api_router
from app.core.config import settings
from app.core.deps import DEV_USER_ID
from app.core.llm.solar import solar_client


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    # ⚠️ **여기서 커리큘럼을 올린다.** `@app.on_event("startup")`으로 두면
    #    안 돈다 — FastAPI는 `lifespan=`이 주어지면 구형 on_event 핸들러를
    #    **조용히 무시한다.** 병합은 성공했는데 자료가 0개였고, 화면만 비어서
    #    원인이 안 보였다(통합 1단계에서 실제로 겪었다).
    _load_curriculum()
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


def _load_curriculum() -> None:
    """픽스처로 자료를 올리고, 있으면 진도 스냅샷을 복원한다.

    DB가 붙기 전까지의 임시 경로다. 파싱 팀과 통합하면 업로드로 바뀐다.
    fixture·스냅샷이 없어도 서버는 떠야 하므로 실패를 삼킨다.
    """
    from app.features.curriculum.store import store

    try:
        loaded = store.load_fixtures()
        print(f"[curriculum] 자료 {len(loaded)}개 로드: {', '.join(loaded)}")
    except Exception as e:  # noqa: BLE001
        print(f"[curriculum] 로드 실패(무시하고 계속): {type(e).__name__}: {e}")
        return

    # 진도는 이제 사용자별이라 여기서 다 읽지 않는다 — 요청이 들어올 때
    # 그 사람 것만 읽는다(`store.progress_of`). 여기서 할 일은 사용자 구분이
    # 없던 시절의 단일 스냅샷을 dev 유저 몫으로 옮기는 것뿐이고, 그것도 한 번뿐이다.
    try:
        n = store.migrate_legacy_progress(str(DEV_USER_ID))
        if n:
            print(f"[curriculum] 예전 진도 스냅샷을 dev 유저로 이관: 화면 {n}개")
    except Exception as e:  # noqa: BLE001
        print(f"[curriculum] 진도 이관 실패(무시하고 계속): {type(e).__name__}: {e}")

    from app.features.curriculum.profile import explain as profile_explain

    tips = profile_explain(store.profile)
    if tips:
        print(f"[curriculum] 성향 fixture: {', '.join(tips)}")
    else:
        print("[curriculum] 성향 fixture: 중립(지시 없음)")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
