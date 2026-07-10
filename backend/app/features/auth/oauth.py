"""OAuth 소셜 로그인 — 제공자별 엔드포인트 + 토큰교환/유저정보 정규화.

지원: Google, Naver. Authorization Code 흐름(서버측 교환).
1) authorize_url()로 제공자 동의화면 URL 조립 → 사용자 리다이렉트
2) 콜백에서 받은 code를 exchange_and_fetch()에 넘겨 access_token 교환 →
   유저정보 조회 → {sub, email, name}로 정규화해 반환

client_id/secret는 settings(.env)에서 온다. 미설정 제공자는 라우터에서 503.
"""
from dataclasses import dataclass

import httpx
from fastapi import HTTPException

from app.core.config import settings


@dataclass(frozen=True)
class ProviderConfig:
    authorize_url: str
    token_url: str
    userinfo_url: str
    scope: str


_PROVIDERS: dict[str, ProviderConfig] = {
    "google": ProviderConfig(
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        scope="openid email profile",
    ),
    "naver": ProviderConfig(
        authorize_url="https://nid.naver.com/oauth2.0/authorize",
        token_url="https://nid.naver.com/oauth2.0/token",
        userinfo_url="https://openapi.naver.com/v1/nid/me",
        scope="",
    ),
}

_TIMEOUT = 10.0


@dataclass(frozen=True)
class OAuthUser:
    sub: str
    email: str
    name: str | None


def supported_providers() -> list[str]:
    return list(_PROVIDERS)


def _credentials(provider: str) -> tuple[str, str]:
    if provider == "google":
        return settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET
    if provider == "naver":
        return settings.NAVER_CLIENT_ID, settings.NAVER_CLIENT_SECRET
    raise HTTPException(status_code=404, detail=f"알 수 없는 제공자: {provider}")


def is_configured(provider: str) -> bool:
    client_id, client_secret = _credentials(provider)
    return bool(client_id.strip() and client_secret.strip())


def redirect_uri(provider: str) -> str:
    return f"{settings.OAUTH_BACKEND_BASE_URL}/api/auth/callback/{provider}"


def authorize_url(provider: str, state: str) -> str:
    """제공자 동의화면 URL 조립."""
    cfg = _get(provider)
    client_id, _ = _credentials(provider)
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri(provider),
        "state": state,
    }
    if cfg.scope:
        params["scope"] = cfg.scope
    query = httpx.QueryParams(params)
    return f"{cfg.authorize_url}?{query}"


async def exchange_and_fetch(provider: str, code: str, state: str) -> OAuthUser:
    """code → access_token 교환 → 유저정보 조회 → 정규화."""
    cfg = _get(provider)
    client_id, client_secret = _credentials(provider)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        token_resp = await client.post(
            cfg.token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri(provider),
                "state": state,  # google은 무시, naver는 필요
            },
            headers={"Accept": "application/json"},
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="토큰 교환 실패(제공자 응답 오류).")
        access_token = (token_resp.json() or {}).get("access_token")
        if not access_token:
            raise HTTPException(status_code=502, detail="access_token을 받지 못했습니다.")

        info_resp = await client.get(
            cfg.userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if info_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="유저 정보 조회 실패.")
        return _normalize(provider, info_resp.json() or {})


def _get(provider: str) -> ProviderConfig:
    cfg = _PROVIDERS.get(provider)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"알 수 없는 제공자: {provider}")
    return cfg


def _normalize(provider: str, data: dict) -> OAuthUser:
    if provider == "google":
        sub = data.get("sub")
        email = data.get("email")
        name = data.get("name")
    elif provider == "naver":
        # 네이버는 {resultcode, message, response: {...}} 로 감싼다.
        r = data.get("response") or {}
        sub = r.get("id")
        email = r.get("email")
        name = r.get("name") or r.get("nickname")
    else:  # 도달 불가(위에서 검증)
        raise HTTPException(status_code=404, detail=f"알 수 없는 제공자: {provider}")

    if not sub or not email:
        raise HTTPException(
            status_code=502,
            detail="제공자가 필수 정보(id/email)를 주지 않았습니다. 동의 항목(이메일)을 확인하세요.",
        )
    return OAuthUser(sub=str(sub), email=str(email), name=str(name) if name else None)
