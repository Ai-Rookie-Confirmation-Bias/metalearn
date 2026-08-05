"""전역 환경 설정: .env / 환경변수 파싱 (pydantic-settings)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # DB (compose의 environment에서 주입)
    DATABASE_URL: str = "postgresql+psycopg://postgres:dev@db:5432/metalearn"

    # 인증
    SECRET_KEY: str = "change-me-in-env"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

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

    # CORS (프론트 dev 서버)
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # 업로드 원본 저장 경로 (컨테이너 내부)
    UPLOAD_DIR: str = "/app/uploads"


settings = Settings()
