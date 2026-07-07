### 🌐 Frontend (React + Vite) 폴더 구조도

```text
frontend/src/
├── app/                        # ⚙️ 앱 전체 뼈대 및 초기 설정
│   ├── routes.tsx              # URL ↔ 페이지 연결 지도
│   └── queryClient.ts          # React Query 전역 통신 설정
│
├── pages/                      # 📄 URL과 1:1 매칭되는 실제 화면 (껍데기 레이아웃)
│   ├── DashboardPage.tsx       # /dashboard 에 띄울 페이지 (내부 로직은 없음)
│   └── LearningPage.tsx        # /learn 에 띄울 페이지
│
├── features/                   # ⭐ 핵심! 도메인(기능)별 비즈니스 로직 모음
│   ├── learning/               # [학습 루프 기능]
│   │   ├── api.ts              # 📡 서버의 /attempts 에 정답 보내는 통신 함수
│   │   ├── store.ts            # 🧠 입력 중인 텍스트, 모달 상태 등 UI 임시 기억상자
│   │   └── components/         # 🧩 LearningBlock.tsx 등 이 기능 전용 UI 조각들
│   │
│   └── dashboard/              # [대시보드 기능]
│       ├── api.ts              # 📡 통계 데이터 가져오는 통신 함수
│       └── components/         # 🧩 통계 차트 전용 UI 조각들
│
├── shared/                     # 🧰 프로젝트 전체 공용 자재 창고
│   ├── api/                    
│   │   └── client.ts           # 🌐 공통 Axios (Base URL, 토큰 자동부여, 에러 처리)
│   ├── ui/                     # 🎨 공용 컴포넌트 (Button, Card, Input 등)
│   ├── styles/                 # 🖌️ 글로벌 CSS, 폰트, 색상 변수 (global.css)
│   └── utils/                  # 🛠️ 도우미 함수 (날짜 계산, network.ts 등)
│
└── runtime/                    # 🔌 MetaLearn 전용 온/오프라인 분기 엔진
    ├── provider.ts             # 📡 현재 인터넷 켜졌는지 꺼졌는지 판단
    └── engine.ts               # 💻 오프라인일 때 로컬 EXAONE 돌리는 로직
```

---

### ⚙️ Backend (FastAPI) 폴더 구조도

```text
backend/app/
├── main.py                     # 🚀 서버 실행 진입점 (FastAPI 앱 객체 생성)
├── api.py                      # 🔗 각 features의 라우터들을 /api/v1/.. 으로 묶어주는 곳
│
├── core/                       # ⚙️ 백엔드 전체 공통 시스템 
│   ├── config.py               # 🔑 환경변수 (.env) 불러오기
│   ├── database.py             # 🗄️ PostgreSQL(pgvector) DB 연결 설정
│   ├── security.py             # 🛡️ 비밀번호 암호화 및 JWT 토큰 처리
│   ├── verify_grade.py         # ⚖️ 생성된 사실 검증 및 채점 공통 로직
│   └── llm/                    # 🤖 AI 호출 공통 인터페이스 (solar.py 등)
│
└── features/                   # ⭐ 핵심! 도메인(기능)별 API 모음
    ├── learning/               # [학습 처리 기능]
    │   ├── router.py           # 🚪 도착지: @router.post("/attempts") 요청 받는 곳
    │   ├── schemas.py          # 📦 형태 검사: 들어온 JSON 데이터가 규칙에 맞는지(Pydantic)
    │   ├── service.py          # 🧠 두뇌: 실제 정답을 확인하고 다음 복습일을 계산하는 연산
    │   └── models.py           # 🗄️ DB 매핑: PostgreSQL attempts 테이블 정의
    │
    └── materials/              # [문서 업로드 및 RAG 처리 기능]
        ├── router.py           # 🚪 도착지: @router.post("/documents")
        ├── schemas.py          # 📦 형태 검사
        └── service.py          # 🧠 두뇌: PDF 텍스트 파싱 및 쪼개기(RAG) 연산
```

이 그림을 머릿속에 담아두시면, "버튼 디자인을 고쳐야 해" 👉 `frontend/src/shared/ui/`
"학습 화면에서 정답 보내는 로직이 이상해" 👉 `frontend/src/features/learning/` 
"AI 채점 결과가 DB에 안 들어가" 👉 `backend/app/features/learning/service.py` 
