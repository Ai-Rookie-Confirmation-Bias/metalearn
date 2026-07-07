# MetaLearn

하이브리드(클라우드 + 로컬) AI 학습 플랫폼. 온라인일 땐 백엔드가 Upstage Solar로 학습 콘텐츠를 생성하고, 오프라인일 땐 브라우저 내 로컬 LLM(EXAONE)으로 동작하는 것을 목표로 한다.

> **현재 상태: 기본 골격(skeleton) / MVP 출발점.**
> 클라우드(Solar) 경로 위주로 구조만 잡혀 있고, 로컬 EXAONE 런타임은 **Phase 2**로 스텁만 존재한다.
> `learning` 도메인만 "이렇게 만들면 된다"는 동작 예시로 채워져 있고, 나머지 도메인은 빈 골격이다.

---

## 기술 스택

| 구분 | 기술 | 역할 |
| --- | --- | --- |
| Frontend | React 19, Vite 6, TypeScript, pnpm | SPA, 빠른 HMR |
| 상태관리 | TanStack Query 5, Zustand 5 | (Query) 서버 데이터 캐시 / (Zustand) UI 상태 |
| 라우팅 | react-router-dom 7 | URL ↔ 페이지 매핑 |
| 로컬 저장 | Dexie (IndexedDB) | 오프라인 영속 — **Phase 2** |
| Backend | Python 3.12, FastAPI, uv | 비즈니스 로직, Pydantic 검증, AI 연동 |
| ORM/검증 | SQLAlchemy 2.0, Pydantic 2 | DB 매핑 / DTO |
| DB | PostgreSQL 16 + pgvector | 관계형 + 벡터(RAG) 저장, `halfvec` |
| 마이그레이션 | Alembic | 스키마 버전 관리 |
| AI (Cloud) | Upstage Solar | 메인 생성 엔진 (OpenAI 호환 API) |
| AI (Local) | EXAONE (wllama/WebGPU) | 오프라인/무료 — **Phase 2, 스텁** |
| Infra | Docker, Docker Compose | 프론트/백/DB 컨테이너 오케스트레이션 |

---

## 실행 방법

```bash
# 전체 빌드 & 기동
docker compose up --build
```

| 서비스 | 주소 |
| --- | --- |
| Frontend (Vite dev) | http://localhost:5173 |
| Backend (FastAPI) | http://localhost:8000 |
| API 헬스체크 | http://localhost:8000/api/health → `{"status":"ok"}` |
| API 문서 (Swagger) | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 (user `postgres` / pw `dev` / db `metalearn`) |

### DB 테이블 생성 (최초 1회 / 모델 변경 시)

```bash
# pgvector 확장 활성화 + 마이그레이션 적용
docker compose exec backend uv run alembic upgrade head

# 모델 추가/변경 후 새 마이그레이션 생성
docker compose exec backend uv run alembic revision --autogenerate -m "메시지"
```

### 환경변수

- `backend/.env` — `SECRET_KEY`, `UPSTAGE_API_KEY` 등 시크릿. (`DATABASE_URL`은 compose에서 주입하므로 여기 둘 필요 없음)
- `frontend/.env` — `VITE_API_BASE_URL` (기본 `http://localhost:8000`)
- 둘 다 `.gitignore`로 커밋 제외됨. Solar 호출(`/api/learning/generate`)은 `UPSTAGE_API_KEY`가 있어야 끝까지 동작한다. (헬스체크·문서·프론트 기동에는 불필요)

---

## 전체 폴더 구조

```
metalearn/
├── docker-compose.yml          # 프론트/백/DB 오케스트레이션
├── .gitignore / .gitattributes
├── README.md
│
├── backend/                    # FastAPI (Python 3.12 + uv)
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── .env                    # 시크릿 (커밋 금지)
│   ├── pyproject.toml          # 의존성 명세
│   ├── alembic.ini             # 마이그레이션 설정
│   ├── alembic/
│   │   ├── env.py              # settings에서 DB URL·모델 메타데이터 주입
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 0001_init_pgvector.py   # CREATE EXTENSION vector
│   └── app/
│       ├── __init__.py
│       ├── main.py             # FastAPI 인스턴스, CORS, 라우터 등록, /api/health
│       ├── api.py              # features/* 라우터를 /api로 통합
│       ├── core/               # 공통 시스템 모듈
│       │   ├── config.py       # pydantic-settings로 .env/환경변수 파싱
│       │   ├── database.py     # engine, SessionLocal, Base, get_db
│       │   ├── security.py     # JWT 발급·검증, 패스워드 해싱
│       │   └── llm/
│       │       ├── base.py     # LLMClient 추상 인터페이스
│       │       └── solar.py    # Upstage Solar 구현체
│       └── features/           # 도메인별 격리 구역
│           ├── auth/           # router (빈 골격)
│           ├── seed/           # router (빈 골격)
│           ├── materials/      # router (빈 골격)
│           ├── review/         # router (빈 골격)
│           └── learning/       # ★ 5레이어 동작 예시 (전부 채워짐)
│               ├── router.py       # [1] Controller — POST /api/learning/generate
│               ├── schemas.py      # [2] DTO — Pydantic 입출력
│               ├── service.py      # [3] Service — 비즈니스 로직 + LLM 호출
│               ├── repository.py   # [4] Repository — DB/pgvector 쿼리
│               └── models.py       # [5] Entity — SQLAlchemy 테이블 (halfvec 컬럼)
│
└── frontend/                   # React 19 + Vite (FSD 구조)
    ├── Dockerfile
    ├── .dockerignore
    ├── .env                    # VITE_API_BASE_URL
    ├── package.json            # packageManager: pnpm@10.12.3 고정
    ├── pnpm-lock.yaml
    ├── tsconfig.json           # paths: "@/*" → "src/*"
    ├── vite.config.ts          # server.host true, port 5173
    ├── index.html
    └── src/
        ├── main.tsx            # 진입점 — QueryClientProvider + RouterProvider
        ├── App.tsx             # 루트 레이아웃 (Outlet)
        ├── vite-env.d.ts
        ├── app/                # 전역 셋업
        │   ├── routes.tsx      # createBrowserRouter
        │   └── queryClient.ts  # TanStack Query 전역 옵션
        ├── pages/
        │   └── LearningPage.tsx    # features 컴포넌트 조립 (URL과 1:1)
        ├── shared/             # 도메인 비종속 공용 자원
        │   ├── ui/Button.tsx       # 디자인 시스템
        │   ├── api/client.ts       # Axios 공통 인스턴스 + 인터셉터
        │   └── utils/network.ts    # 온/오프라인 판단 (provider 분기용)
        ├── storage/
        │   └── db.ts           # Dexie/IndexedDB 초기화 — Phase 2
        ├── runtime/            # ★ 하이브리드 AI 분기
        │   ├── provider.ts     # 온라인→API / 오프라인→로컬 엔진 분기
        │   └── engine.ts       # 로컬 EXAONE 엔진 — Phase 2 스텁
        └── features/
            ├── seed/           # .gitkeep (빈 골격)
            ├── review/         # .gitkeep (빈 골격)
            └── learning/       # ★ 동작 예시 (전부 채워짐)
                ├── api/requestGenerate.ts      # [1] provider 호출 함수
                ├── queries/useGenerate.ts      # [2] TanStack Query 훅
                ├── components/TutorPanel.tsx   # [3] UI (queries만 호출)
                ├── store.ts                    # Zustand UI 상태
                └── prompts.ts                  # 로컬 엔진용 프롬프트 (Phase 2)
```

### 채워진 것 vs 빈 골격

| 영역 | 상태 |
| --- | --- |
| 인프라 (compose, Dockerfile ×2, .env, .gitignore) | ✅ 동작 |
| backend `core/` (config, database, security, llm) | ✅ 동작 |
| backend `features/learning/` | ✅ 데모(generate) + JIT 적응형 커리큘럼(점수 분기 선수+브릿지 / 메인100%, 인출형 블록) |
| backend `features/materials/` | ✅ Ingestion 파이프라인 (PDF→파싱→개념/선수지식 그래프→pgvector) |
| backend `features/diagnostic/` | ✅ BKT 정밀 진단 (불확실성 타겟팅 + MCQ/빈칸/역질문 혼합 + LLM 심판 채점 + 유형별 추측률 + 신뢰도 수렴) |
| backend `features/{auth,seed,review}/` | ⬜ 빈 `router.py`만 (엔드포인트 0) |
| frontend `app/`·`shared/`·`pages/`·`runtime(online)` | ✅ 동작 |
| frontend `features/learning/` | ✅ 데모 패널 + JIT 커리큘럼 뷰(인출형 블록, `/curriculum`) |
| frontend `features/materials/` | ✅ 업로드 패널 + 개념 그래프 뷰 (`/materials`) |
| frontend `features/diagnostic/` | ✅ 진단 루프 UI + 숙련도 패널 (`/diagnostic`) |
| frontend `features/{seed,review}/` | ⬜ `.gitkeep`만 |
| 로컬 EXAONE (`runtime/engine.ts`), Dexie (`storage/db.ts`) | ⬜ Phase 2 스텁 |

> `__init__.py`는 파이썬 패키지 표식(빈 파일, 삭제 금지). 백엔드 폴더마다 존재.

---

## 데이터 흐름

```
[브라우저]
  features/learning/components/TutorPanel  (UI)
        └─ queries/useGenerate            (TanStack Query)
              └─ api/requestGenerate
                    └─ runtime/provider   ★ 온/오프라인 분기
                          ├─ 온라인 → shared/api/client (axios) → 백엔드
                          └─ 오프라인 → runtime/engine (로컬 EXAONE, Phase 2)

[백엔드]  POST /api/learning/generate
  router → schemas(검증) → service → core/llm/solar (Upstage Solar)
                              └─ repository → PostgreSQL + pgvector

[DB]  pgdata 볼륨에 영속 (docker compose down -v 시 삭제 주의)
```

---

## 이번 세팅에서 변경/추가된 내역 (git 기준)

### 수정된 기존 파일

- **`docker-compose.yml`** — 주석 1줄 → 전체 작성. db(pgvector pg16, healthcheck `pg_isready -U postgres -d metalearn`) + backend(`DATABASE_URL`을 environment로 주입, `./backend:/app` + 익명볼륨 `/app/.venv`) + frontend(`CHOKIDAR_USEPOLLING`, `/app/node_modules` 익명볼륨) + `pgdata` 볼륨.
- **`backend/Dockerfile`** — 주석 1줄 → 작성. `python:3.12-slim`, `pip install uv`, `COPY pyproject.toml uv.lock*` 후 **`uv sync`** (uv.lock 미존재 시 빌드 중 생성), venv를 PATH에 추가.
  - ⚠️ ready 계획의 `uv sync --frozen`에서 변경: 로컬에 uv가 없어 `uv.lock`을 사전 생성하지 못함 → 첫 빌드 때 컨테이너가 lock 생성. **lock 커밋 후 `--frozen`으로 되돌리는 것을 권장.**
- **`frontend/Dockerfile`** — 주석 1줄 → 작성. `node:20-slim`, `corepack enable && corepack prepare pnpm@10.12.3 --activate`(버전 고정), `pnpm install --frozen-lockfile`.
- **`.gitignore`** — `.env.*`, `*.pyc`, `.venv/`, `dist/`, `.DS_Store` 등 보강.
- **`README.md`** — (이 문서) ready.md 설계 메모 → 실제 골격 문서로 재작성.

### 새로 추가된 파일 (untracked)

- backend: `pyproject.toml`, `.dockerignore`, `alembic.ini`, `alembic/`(env.py·script.py.mako·versions/0001_init_pgvector.py), `app/` 전체(main, api, core/*, features/*), `.env`(시크릿, gitignore)
- frontend: `package.json`, `pnpm-lock.yaml`, `tsconfig.json`, `vite.config.ts`, `index.html`, `.dockerignore`, `src/` 전체, `.env`(gitignore)

### 설계 대비 결정사항

- **도메인 네이밍 통일**: 프론트 `curriculum` → `seed` (백엔드 기준).
- **로컬 EXAONE**: Phase 2로 보류. `runtime/provider.ts`는 온라인 분기만 구현, `engine.ts`는 스텁.
- **pnpm 빌드 스크립트**: `package.json`의 `pnpm.onlyBuiltDependencies: ["esbuild"]` 추가 — pnpm 10이 esbuild 빌드 스크립트를 차단해 Vite가 안 뜨는 문제 방지.

---

## 검증 상태

- ✅ 프론트 의존성 설치 + `pnpm-lock.yaml` 생성, `tsc --noEmit` 타입체크 통과, Vite 6.4 기동 확인
- ✅ 백엔드 전체 Python 컴파일 통과 (`py_compile`)
- ⚠️ 백엔드 의존성 실제 설치/기동은 도커 빌드 시 검증됨 (로컬 uv 미설치)

