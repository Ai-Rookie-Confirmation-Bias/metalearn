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
    _strand_orphaned_parses()
    _load_curriculum()
    yield
    # Solar 공유 커넥션 풀 정리
    await solar_client.aclose()


def _strand_orphaned_parses() -> None:
    """죽은 프로세스가 두고 간 파싱을 실패로 도장 찍는다.

    파싱은 `BackgroundTasks`로 **이 프로세스 안에서** 돈다. 서버가 내려가면
    (docker compose down, --reload 재시작, 크래시) 그 작업은 그냥 사라지는데,
    문서는 `extracting` 같은 중간 상태로 남는다. 되살릴 사람이 아무도 없다.

    화면은 그 상태를 "아직 진행 중"으로 읽어 **영원히 폴링한다.** 실측:
    자료 1개가 `extracting`에서 멈춘 채 진행바 80%로 굳었다.

    실패로 바꾸면 두 가지가 풀린다 — 카드가 치우기를 내주고, 같은 파일을 다시
    올리면 `register()`가 재파싱한다(`needs_parse`가 PENDING·FAILED를 본다).

    ⚠️ 재개가 아니라 **포기**다. 원본 바이트를 안 들고 있어서 이어서 못 한다.
    """
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.features.parsing.models import DocStatus, Document

    settled = {DocStatus.READY.value, DocStatus.FAILED.value}
    db = SessionLocal()
    try:
        rows = list(
            db.scalars(select(Document).where(Document.status.notin_(settled)))
        )
        if not rows:
            return
        for row in rows:
            row.status = DocStatus.FAILED.value
            row.error = "서버가 다시 시작되어 분석이 끊겼습니다. 다시 올려 주세요."
        db.commit()
        print(f"[parsing] 끊긴 파싱 {len(rows)}건을 실패로 정리: "
              + ", ".join(r.filename[:24] for r in rows))
    except Exception as exc:  # noqa: BLE001 — 부팅을 막지 않는다
        db.rollback()
        print(f"[parsing] 끊긴 파싱 정리 실패: {type(exc).__name__}: {exc}")
    finally:
        db.close()


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
