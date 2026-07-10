> ✅ **병합 완료(2026-07-10, `c97068f` + 마이그 0017→0020 재연결 `17a4653`).** 아래 자격증명 설정 가이드는 계속 유효 — client id/secret만 넣으면 로그인 활성화(`/api/auth/providers`로 확인).

# OAuth 소셜 로그인 (Google / Naver) — 구현 인계 + 설정 가이드

> 작성: 2026-07-08 · 브랜치: `feat/oauth-login` (베이스 `trial/full-assembly-v2`)
> 상태: **코드 완성·검증 완료. 실제 로그인은 제공자 client id/secret만 넣으면 동작.**

## 0. 30초 요약

소셜 로그인(구글/네이버) Authorization Code 흐름을 백엔드+프론트에 배선했다.
버튼→백엔드 `/login/{provider}`→제공자 동의화면→백엔드 콜백(코드 교환·유저
find-or-create·JWT 발급)→프론트 `/auth/callback`(#token 저장)→로그인 완료.
기존 `X-User-Id` dev 경로는 **그대로 하위호환**(토큰 없으면 dev 유저).
남은 건 제공자 콘솔 앱 등록 + `.env` 키 4개뿐.

## 1. 지금 해야 할 것 (동작시키려면)

### ① 제공자 콘솔에서 앱 등록 + Redirect URI 등록
- **Google** — [Google Cloud Console](https://console.cloud.google.com) → API 및 서비스 → 사용자 인증 정보 → OAuth 2.0 클라이언트 ID 생성.
  - 승인된 리디렉션 URI: `http://localhost:58001/api/auth/callback/google`
  - OAuth 동의 화면에서 `email`, `profile` 스코프 허용.
- **Naver** — [네이버 개발자센터](https://developers.naver.com/apps) → 애플리케이션 등록 → "네이버 로그인" 사용.
  - Callback URL: `http://localhost:58001/api/auth/callback/naver`
  - 필수 제공 정보: **이메일 주소**(필수 체크 — 없으면 로그인 실패), 이름.

> 포트 주의: 위 URI의 `58001`은 **트라이얼 스택(mlv2)** 백엔드 포트다. 일반
> 스택(8000)에서 쓰면 `.../callback/{provider}`의 호스트를 그 포트로 등록하고
> `OAUTH_BACKEND_BASE_URL`도 맞춰야 한다.

### ② `backend/.env`에 키 4개 추가
```dotenv
GOOGLE_CLIENT_ID=발급받은_값
GOOGLE_CLIENT_SECRET=발급받은_값
NAVER_CLIENT_ID=발급받은_값
NAVER_CLIENT_SECRET=발급받은_값
# (선택) 스택 포트가 다르면
OAUTH_BACKEND_BASE_URL=http://localhost:58001
FRONTEND_BASE_URL=http://localhost:55173
```
넣고 백엔드만 재시작(`docker compose -p mlv2 restart backend`)하면 끝.
`GET /api/auth/providers`가 `{"google":true,"naver":true}`로 바뀌면 준비 완료.

## 2. 흐름 / 엔드포인트

```
[AuthPage 버튼] --GET--> /api/auth/login/{provider}      (302 → 제공자 동의화면)
        제공자 --302--> /api/auth/callback/{provider}?code&state
                         ├ state 검증(우리 SECRET_KEY 서명 JWT)
                         ├ code→access_token 교환 → 유저정보 조회
                         ├ 유저 find-or-create (provider+sub, 이메일 연결)
                         └ 우리 JWT 발급
        --302--> {FRONTEND}/auth/callback#token=<JWT>&provider=...
[AuthCallbackPage] token을 localStorage(ml_access_token)에 저장 → /library
이후 모든 API 요청: Authorization: Bearer <JWT> (client.ts 인터셉터)
```

- `GET /api/auth/providers` — 제공자별 구성 여부.
- `GET /api/auth/me` — 현재 사용자(JWT 또는 X-User-Id/dev).

## 3. 인증 우선순위 (`core/deps.py`, 하위호환 핵심)

1. `Authorization: Bearer <JWT>` → sub=유저 UUID (정식)
2. `X-User-Id: <UUID>` → 그 유저 (기존 dev/프론트 경로)
3. 둘 다 없으면 `DEV_USER_ID(00000000-...-0001)`

→ 로그인 안 해도 기존처럼 dev 유저로 전부 동작. 토큰 만료 시 프론트
인터셉터가 401에서 토큰을 비워 dev 폴백으로 복귀.

## 4. 변경 파일

**백엔드**
- `features/auth/models.py` — User에 `provider`/`provider_sub`/`name` 추가, `password_hash` nullable, `UniqueConstraint(provider, provider_sub)`.
- `alembic/versions/0017_oauth_user.py` — 위 스키마 마이그레이션(0016→0017).
- `core/config.py` — GOOGLE/NAVER client id·secret, OAUTH_BACKEND_BASE_URL, FRONTEND_BASE_URL.
- `core/security.py` — `decode_access_token()` 추가.
- `core/deps.py` — `get_current_user_id`를 Bearer JWT 우선으로 확장.
- `features/auth/oauth.py` (신규) — 제공자 설정 + 토큰교환/유저정보 정규화.
- `features/auth/repository.py` — `get_or_create_oauth_user()`, `get_by_id()`.
- `features/auth/schemas.py` (신규) — `UserOut`.
- `features/auth/router.py` — `/providers` `/login/{p}` `/callback/{p}` `/me`.

**프론트**
- `shared/api/client.ts` — 토큰 헬퍼(get/set/clear) + 요청 인터셉터(Bearer↔dev).
- `features/auth/api.ts` (신규) — `startLogin` / `fetchMe` / `fetchProviders` / `logout`.
- `pages/AuthCallbackPage.tsx` (신규) — 해시 토큰 저장·에러 표시·리다이렉트.
- `pages/AuthPage.tsx` — 버튼 onClick 배선.
- `app/routes.tsx` — `/auth/callback` 라우트.

## 5. 검증 완료 (2026-07-08, 실행함)

- 마이그 0017 적용, 4개 auth 라우트 노출, 백엔드 리로드 에러 0.
- JWT 발급→디코드 왕복 OK, 위조 토큰→None.
- `get_or_create_oauth_user`: 동일 sub 재로그인→동일 유저, 동일 이메일 타
  provider→기존 계정 연결(중복 가입 방지).
- `/api/auth/providers`=`{google:false,naver:false}`(미설정), `/login/google`=503.
- `/api/auth/me` + Bearer JWT → 200(dev 유저), 위조 Bearer → 401.
- 기존 엔드포인트(`/documents/courses`)가 Bearer/X-User-Id/무인증 모두 200 → **하위호환 확인**.
- 프론트 `tsc --noEmit` 에러 0, `/`·`/auth/callback` 200.

## 6. 남은 논의 / 참고

- **state CSRF**: 현재 state = 우리 SECRET_KEY 서명 JWT(위조 차단). 브라우저
  세션 바인딩(쿠키 nonce)까지는 안 함 — "간단 소셜 로그인" 범위. 강화 필요 시
  콜백에 httpOnly 쿠키 nonce 대조 추가.
- **토큰 저장 위치**: localStorage(XSS 노출면 존재). 더 엄격히 가려면 httpOnly
  쿠키 방식으로 전환 검토.
- **로그아웃 UI / 로그인 상태 표시**: `logout()`·`fetchMe()`는 준비됐고, 헤더/
  사이드바에 사용자 표시·로그아웃 버튼 연결은 후속(요청 시 바로).
- **User.email UNIQUE 기존DB 충돌**(v2 리뷰 §2-1과 연결): 소셜 이메일이 기존
  local 유저 이메일과 같으면 그 계정에 연결된다(의도된 동작). 별개 정책 원하면 조정.
