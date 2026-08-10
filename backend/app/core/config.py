"""전역 환경 설정: .env / 환경변수 파싱 (pydantic-settings)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # DB (compose의 environment에서 주입)
    DATABASE_URL: str = "postgresql+psycopg://postgres:dev@db:5432/metalearn"

    # 인증
    SECRET_KEY: str = "change-me-in-env"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # ── 소셜 로그인 (Google / Naver) ─────────────────────────────
    # 비어 있으면 그 제공자는 "미설정"이다 — /api/auth/providers가 false를 주고
    # 프론트가 버튼을 잠근다. 키를 넣고 백엔드만 재시작하면 켜진다.
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""
    # 콜백 주소를 이 값으로 조립한다 — {OAUTH_BACKEND_BASE_URL}/api/auth/callback/{provider}.
    # **제공자 콘솔에 등록한 Redirect URI와 글자 하나까지 같아야 한다.**
    OAUTH_BACKEND_BASE_URL: str = "http://localhost:8000"
    # 로그인이 끝나면 여기로 돌려보낸다(토큰은 URL 해시로).
    FRONTEND_BASE_URL: str = "http://localhost:5173"

    # ── Upstage Solar ────────────────────────────────────────────
    UPSTAGE_API_KEY: str = ""
    SOLAR_BASE_URL: str = "https://api.upstage.ai/v1"
    SOLAR_CHAT_MODEL: str = "solar-pro3"
    # 비대칭 임베딩: 질의(개념명)와 지문(원문 조각)에 다른 모델을 쓴다.
    SOLAR_EMBED_QUERY_MODEL: str = "embedding-query"
    SOLAR_EMBED_PASSAGE_MODEL: str = "embedding-passage"
    # pgvector 컬럼 차원. 마이그레이션 작성 전 실측으로 확정할 것 —
    # 틀리면 이미 저장된 벡터를 전부 재생성해야 한다.
    SOLAR_EMBED_DIM: int = 4096
    # 주의: "document-parse" 별칭은 최신 출시보다 늦게 갱신된다
    # (기존 실호출 확인: 별칭 → 260128) → 최신 버전을 명시 고정.
    DOCUMENT_PARSE_MODEL: str = "document-parse-260630"

    # ── LG EXAONE (그림 비전 설명 — M3) ──────────────────────────
    EXAONE_API_KEY: str = ""
    EXAONE_BASE_URL: str = ""
    EXAONE_VISION_MODEL: str = ""

    # 같은 파일을 다시 올리면 이미 파싱된 문서를 그대로 쓴다(지문 일치).
    # **끄면 매번 새로 파싱한다** — 파이프라인을 실제로 다시 돌려봐야 할 때만.
    # 문서가 사람 수만큼 쌓이고 파싱 비용도 그만큼 든다.
    REUSE_PARSED_DOCUMENTS: bool = True

    # ── LLM 동시 호출 상한 (프로세스 전역) ───────────────────────
    # 자료를 여러 개 한꺼번에 올리면 **여기가 천장이다.** 문서 하나가 동시 8로
    # 추출하므로 10개면 80을 원하는데, 실제로 나가는 건 이 값만큼이다.
    #
    # 실측 두 점: 40 동시 = 즉시 429 / 8 = 안전. 24로 쓰다가 32로 올렸다 —
    # 429는 _post_retrying 백오프가 흡수하지만, 재시도 로그가 잦으면 내린다.
    # **코드가 아니라 여기서 돌린다** — 429가 보이면 재시작만으로 되돌린다.
    LLM_MAX_CONCURRENT: int = 32
    # 문서 파싱(OCR)은 상한을 따로, 그리고 **훨씬 낮게** 준다.
    #
    # 실측(자료 5개 동시): /chat/completions는 429가 0건인데
    # /document-digitization은 429가 10건, 최대 4차 재시도까지 갔다.
    # 백오프가 2→4→8→16초라 한 콜이 30초를 자면서 슬롯을 물고 있고, 그래서
    # OCR 단계가 20초에서 53초로 늘었다. **OCR은 추론보다 한참 빡빡하다.**
    #
    # 로컬에서 줄 세우는 쪽이 429를 맞고 자는 것보다 낫다 — 자는 동안에는
    # 아무 일도 안 일어나지만, 줄이면 앞 요청이 끝나는 즉시 다음이 나간다.
    LLM_PARSE_CONCURRENT: int = 2

    # 업로드 상한. 넘으면 **받기 전에** 막는다.
    # 실측: 113MB PDF가 업스테이지에서 413. 지금까지는 파일을 다 올리고 파싱을
    # 시작한 뒤에야 영어 HTTP 에러로 실패했다 — 기다린 시간이 통째로 헛일이다.
    MAX_UPLOAD_MB: int = 50

    # ── 파싱 파이프라인 튜닝값 ───────────────────────────────────
    # 조각 하나의 문자 예산. 너무 크면 개념 추출이 뭉뚱그리고, 너무 작으면
    # 호출 수가 폭증한다. 4000자 ≈ 중주제 하나 크기.
    EXTRACTION_SECTION_CHAR_BUDGET: int = 4000
    # 개념 추출 동시 호출 수. Solar 클라 전역 상한과 맞춘다 —
    # 추출은 파싱 비용의 80%라 여기서 놀면 체감 속도가 그대로 죽는다.
    EXTRACTION_MAX_CONCURRENCY: int = 8
    # 이보다 짧은 조각은 개념이 나올 본문이 아니다(목차 스텁, 파트 표지 등).
    # LLM 호출 없이 버린다.
    SEGMENT_MIN_CHARS: int = 200
    # 목차를 만들려면 조각이 최소 이만큼은 있어야 한다.
    #
    # 7단계는 조각을 단원에 배정하는 구조라 **목차 개수 ≤ 조각 개수**다.
    # 실측(network, 43슬라이드 12,850자): 4,000자 예산으로 자르니 조각이 4개뿐이라
    # LLM에게 "단원 3~4개"를 시키게 됐고, 결과가 단원 하나에 조각 하나 —
    # 즉 소제목 나열이 됐다(제목과 내용이 어긋나기까지 했다).
    # 얇은 자료만 예산을 줄여 조각을 확보한다. 두꺼운 자료는 영향이 없다
    # (pilgi 14개 · ryan 19개로 이미 이 값을 넘는다).
    SEGMENT_TARGET_COUNT: int = 12
    # 예산 하한. 이보다 잘게 쪼개면 개념 추출이 문맥을 잃고 호출만 늘어난다.
    SEGMENT_MIN_BUDGET: int = 800
    # 임베딩 배치 크기. 개념 200개를 하나씩 부르면 200콜.
    EMBED_BATCH_SIZE: int = 64
    # 조각 임베딩 입력 절단·배치 (임베딩 모델 토큰 한계 대비).
    SEGMENT_EMBED_MAX_CHARS: int = 2000
    SEGMENT_EMBED_BATCH: int = 16
    # 개념 트리 중첩 깊이 상한(N-2 제한). 초과분은 잘라내 과분할을 막는다.
    MAX_CONCEPT_DEPTH: int = 2
    # 조각(≈3,500자)당 개념 상한. 개념은 학습 단위가 아니라 진단 태그이므로
    # 원문의 모든 용어를 담을 필요가 없다. 자료가 용어 나열형이면 초과할 수
    # 있고, 그건 로그로만 남긴다 — 강제로 자르면 진짜 개념이 사라진다.
    CONCEPT_MAX_PER_SEGMENT: int = 15

    # 목차 상한. 학습 단위로 쓸 크기를 강제한다.
    TOPIC_MAX_COUNT: int = 10

    # ── 개념 중복 판정 (3중 방어) ────────────────────────────────
    # ② 임베딩 최근접: 이 값 이상이면 LLM 판정 없이 즉시 병합.
    CONCEPT_DEDUP_SIM_THRESHOLD: float = 0.92
    # ③ LLM 배치 판정 후보 하한. 실측상 진짜 중복이 0.85~0.92 구간에
    # 별개 개념과 섞여 분포해 단일 문턱으로는 분리가 안 된다
    # → 유사도는 후보 수집만, 판정은 LLM이.
    DEDUP_CANDIDATE_SIM_THRESHOLD: float = 0.85
    DEDUP_MAX_PAIRS: int = 200        # 문서당 후보쌍 상한 (프롬프트 폭주 방지)
    DEDUP_JUDGE_BATCH_SIZE: int = 50  # LLM 판정 1회당 쌍 수

    # ── 12.5 분야 판정 ──────────────────────────────────────────
    # 2회 호출해 **합집합**을 취한다. 교집합이 아니다 — 과목 이름은 임베딩으로
    # 못 가른다는 게 실측으로 확인됐다:
    #   AWS 기본 개념 ↔ AWS 기본 서비스 (같음)  하위포함 0.540 · 이름만 0.806
    #   네트워크 보안 기초 ↔ 네트워크 기초 (다름) 하위포함 0.514 · 이름만 0.866
    # 두 값이 겹쳐서 어느 방식으로도 분리가 안 된다. 놓치면 복구가 안 되고
    # (교집합으로 돌렸을 때 network의 `Linux 기초`가 사라졌다) 헛것은 뒤의
    # 기각 검사(21/21 검증)가 거르므로, 여기서는 회수율을 택한다.
    FIELD_PROBE_RUNS: int = 2
    # 중복 하위 항목을 없애는 문턱. 과목 이름과 달리 하위 항목은 구체적인
    # 명사구라 임베딩이 잘 듣는다. 실측 10쌍으로 잰 값이고 깨끗하게 갈렸다:
    #   같은 것  0.711~0.795  라우팅 기초↔라우팅 원리(0.777), IP 주소 체계↔구조(0.795)
    #   다른 것  0.451~0.679  CIDR 표기법↔서브넷 CIDR 범위 설정(0.679)
    # 이걸 안 걸면 같은 항목이 둘로 남아 기각 판정이 서로 엇갈린다
    # (실측: `라우팅 원리`는 통과인데 `라우팅 기초`는 기각).
    SUBTOPIC_DEDUP_SIM: float = 0.70

    # ── 16' 기각 검사 (선수가 정말 책 밖인가) ────────────────────
    # 임베딩은 **양 끝만 맞고 가운데는 틀린다.** 유사도는 "비슷한 이름의 개념이
    # 있나"를 재지 "이걸 가르치나"를 못 잰다. 실측:
    #   0.783 CIDR 표기법 → CIDR 표기          가르친다 ✓
    #   0.645 라우팅 기초  → 라우팅              전제한다 (오판)
    #   0.539 IP 주소 체계 → IP 주소 범위        전제한다 (오판)
    #   0.468 입출력 장치 관리 → UNIX 커널 기능   전제한다 ✓
    # 0.5~0.75가 섞이는 구간이라 거기만 LLM에게 묻는다(18단계와 같은 구조).
    # 하한 0.50은 첫 실측 경계에서 왔다 — 책 안 최소 0.509 / 책 밖 최대 0.468.
    PREREQ_REJECT_SIM: float = 0.75   # 이 이상이면 자료가 확실히 가르친다
    PREREQ_JUDGE_SIM: float = 0.50    # 이 아래는 확실히 책 밖. 사이는 LLM에게
    PREREQ_JUDGE_BATCH_SIZE: int = 30
    PREREQ_MAX_JUDGE: int = 90        # 코스당 회색 판정 상한

    # ── 18 자료끼리 개념 연결 ───────────────────────────────────
    # pilgi 452개를 ryan 578개에 전부 대조해 잰 값이다.
    #   0.85↑      도커↔Docker, 트랜잭션↔트랜잭션          같은 개념
    #   0.75~0.85  MVC↔모델-뷰-컨트롤러, IDS↔침입탐지      같거나 상하위
    #   0.70~0.75  정규화↔정규화(맞음)와 블루스나프↔블루버그(틀림)가 섞임
    #   0.70↓      MD4↔MD5, 자료구조↔데이터베이스          못 씀
    # dedup의 0.92를 쓰지 않는 이유: 그건 동일 개념 병합이라 보수적이어야
    # 하고, 여기는 "설명을 가져올 만한가"라 상위 개념도 쓸모가 있다.
    LINK_SAME_SIM: float = 0.85
    LINK_RELATED_SIM: float = 0.75
    LINK_JUDGE_SIM: float = 0.70      # 이 아래는 묻지도 않는다
    LINK_JUDGE_BATCH_SIZE: int = 50   # 회색지대 LLM 확인 1회당 쌍 수
    LINK_MAX_JUDGE_PAIRS: int = 200   # 문서쌍당 LLM 확인 상한

    # 문제은행 생성·검증에 쓰는 모델.
    #
    # 두 모델의 출력 형태가 다르다(실측):
    #     solar-pro2  ```json [ {...}, {...} ] ```   ← 배열, 코드펜스
    #     solar-pro3  {...}{...}                     ← 객체를 이어붙임
    # 통합 시점엔 파서가 앞의 형태만 읽어 pro3에서 문항이 0개였다.
    # 지금은 core/quality/parsing.py::extract_json이 이어붙임도 배열로 건진다
    # (quiz 담당 확정 2026-08-07 — 품질 실측은 QUIZ_TUNING §12).
    QUIZ_CHAT_MODEL: str = "solar-pro3"

    # 교차 검증용 EXAONE (OpenAI 호환 엔드포인트 — 키가 있으면 검증 모델로 사용)
    EXAONE_API_KEY: str = ""
    EXAONE_BASE_URL: str = "https://api.friendli.ai/serverless/v1"
    EXAONE_MODEL: str = "LGAI-EXAONE/K-EXAONE-236B-A23B"

    # CORS (프론트 dev 서버)
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # 업로드 원본 저장 경로 (컨테이너 내부)
    UPLOAD_DIR: str = "/app/uploads"


settings = Settings()
