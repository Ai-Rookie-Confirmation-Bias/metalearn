"""인증 라우터 — 소셜 로그인(Google/Naver)과 현재 사용자.

  GET /api/auth/providers          제공자별 구성 여부 (버튼 활성화 판단)
  GET /api/auth/login/{provider}   제공자 동의화면으로 302
  GET /api/auth/callback/{p}       code 교환 → 유저 find-or-create → 프론트로 302
  GET /api/auth/me                 지금 요청이 누구 것인가

state는 우리 SECRET_KEY로 서명한 JWT다 — 제공자를 왕복하는 사이 위조를 막는다.
브라우저 세션 바인딩(쿠키 nonce)까지는 안 한다.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.security import create_access_token, decode_access_token
from app.features.auth import oauth
from app.features.auth.repository import AuthRepository
from app.features.auth.schemas import UserOut

router = APIRouter()

_STATE_PREFIX = "oauth-state:"


@router.get("/providers")
def providers() -> dict[str, bool]:
    """키가 채워진 제공자만 true. 프론트는 false인 버튼을 잠근다."""
    return {p: oauth.is_configured(p) for p in oauth.supported_providers()}


@router.get("/login/{provider}")
def login(provider: str) -> RedirectResponse:
    if provider not in oauth.supported_providers():
        raise HTTPException(status_code=404, detail=f"지원하지 않는 제공자: {provider}")
    if not oauth.is_configured(provider):
        raise HTTPException(
            status_code=503,
            detail=f"{provider} 로그인이 설정되지 않았습니다(.env에 client id/secret 필요).",
        )
    state = create_access_token(f"{_STATE_PREFIX}{provider}")
    return RedirectResponse(oauth.authorize_url(provider, state), status_code=302)


@router.get("/callback/{provider}")
async def callback(
    provider: str,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """실패해도 500을 던지지 않는다 — 사용자는 브라우저로 여기 도착해 있다.

    사유를 해시에 담아 프론트 콜백 화면으로 보내고, 거기서 사람이 읽을
    문장으로 바꾼다.
    """
    front = settings.FRONTEND_BASE_URL.rstrip("/")

    def fail(reason: str) -> RedirectResponse:
        return RedirectResponse(f"{front}/auth/callback#error={reason}", status_code=302)

    if error:
        return fail("denied")  # 제공자 화면에서 취소했다
    if provider not in oauth.supported_providers():
        return fail("unknown_provider")
    if not code or not state:
        return fail("missing_code")
    if decode_access_token(state) != f"{_STATE_PREFIX}{provider}":
        return fail("bad_state")

    try:
        info = await oauth.exchange_and_fetch(provider, code, state)
    except HTTPException:
        return fail("exchange_failed")

    user = AuthRepository(db).get_or_create_oauth_user(
        provider=provider,
        provider_sub=info.sub,
        email=info.email,
        name=info.name,
    )
    db.commit()

    token = create_access_token(str(user.id))
    return RedirectResponse(
        f"{front}/auth/callback#token={token}&provider={provider}", status_code=302
    )


@router.get("/me", response_model=UserOut)
def me(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> UserOut:
    """미로그인이면 dev 유저가 온다. **에러가 아니다** — 헤더가 로그인 여부를
    이걸로 그리는데 404를 주면 로그인 전 화면이 깨진 것처럼 보인다."""
    user = AuthRepository(db).get_by_id(user_id)
    if user is None:  # 의존성이 존재를 보장한다. 여기 오면 그 사이에 지워진 것
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return UserOut.model_validate(user)
