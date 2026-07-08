"""인증 라우터 — OAuth 소셜 로그인(Google/Naver) + 현재 사용자 조회.

흐름:
  GET /api/auth/login/{provider}      → 제공자 동의화면으로 302 리다이렉트
  GET /api/auth/callback/{provider}   → code 교환 → 유저 find-or-create →
                                        JWT 발급 → 프론트로 302 (#token=...)
  GET /api/auth/me                    → 현재 로그인 사용자(JWT/헤더 기반)

state는 우리 SECRET_KEY로 서명한 JWT — 제공자 왕복 간 위조를 막는다(CSRF 완화).
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
def providers() -> dict:
    """구성된(로그인 가능한) 제공자 목록 — 프론트가 버튼 활성화 판단에 사용."""
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
    front = settings.FRONTEND_BASE_URL.rstrip("/")

    def fail(reason: str) -> RedirectResponse:
        return RedirectResponse(f"{front}/auth/callback#error={reason}", status_code=302)

    if error:
        return fail("denied")  # 사용자가 제공자 화면에서 취소/거부
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
    user = AuthRepository(db).get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return UserOut.model_validate(user)
