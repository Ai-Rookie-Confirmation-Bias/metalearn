"""전역 환경 설정: .env / 환경변수 파싱 (pydantic-settings)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # DB (compose의 environment에서 주입)
    DATABASE_URL: str = "postgresql+psycopg://postgres:dev@db:5432/metalearn"

    # 인증
    SECRET_KEY: str = "change-me-in-env"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # 외부 LLM
    UPSTAGE_API_KEY: str = ""
    SOLAR_BASE_URL: str = "https://api.upstage.ai/v1"
    SOLAR_CHAT_MODEL: str = "solar-pro3"
    SOLAR_EMBED_MODEL: str = "embedding-query"
    SOLAR_EMBED_DIM: int = 4096
    DOCUMENT_PARSE_MODEL: str = "document-parse"

    # 개념 추출 깊이 상한.
    # 명세의 "N-2 깊이 제한" — 문서 목차 깊이(N)보다 2단계 얕게 파편화해
    # 과분할/노이즈를 막는다. 추출 스키마(재귀 ConceptNode)에서 강제.
    MAX_CONCEPT_DEPTH: int = 2

    # ── BKT(베이지안 지식 추적) 진단 ──────────────────────────────
    # 개념별 사전 숙련 확률 / 학습전이 / 슬립(앎에도 틀림) / 추측(모름에도 맞춤).
    # 진단 모드는 '측정'이 목적이라 학습전이(p_transit)는 0으로 둔다.
    BKT_P_INIT: float = 0.30
    BKT_P_TRANSIT: float = 0.0
    BKT_P_SLIP: float = 0.10
    BKT_P_GUESS: float = 0.25  # 기본/4지선다 추측률 ≈ 0.25
    # 문항 유형별 추측률(p_guess). 인출형일수록 운으로 맞을 확률이 낮아
    # BKT가 더 빠르고 정확히 수렴한다 → 진단 정확도 ↑.
    BKT_GUESS_MCQ: float = 0.25
    BKT_GUESS_CLOZE: float = 0.05
    BKT_GUESS_INVERSE: float = 0.02
    # 신뢰도 확정 경계: p>=HIGH(앎) 또는 p<=LOW(모름)면 해당 개념 진단 종료.
    BKT_RESOLVE_HIGH: float = 0.90
    BKT_RESOLVE_LOW: float = 0.10
    # 개념당 안전 상한 (그래프 전파로 대부분의 개념이 빠르게 수렴하므로 낮게 설정).
    BKT_MAX_QUESTIONS_PER_CONCEPT: int = 5
    # 세션 시작 시 개념당 미리 생성할 문항 수. 게이티드 모드는 개념당 1문항으로
    # 판정하므로 1이면 불필요한 생성이 없다.
    BKT_POOL_SIZE_PER_CONCEPT: int = 1
    # 배치 생성 시 한 번의 LLM 호출에 넣을 개념 수 (토큰 한도 대비).
    BKT_BATCH_CONCEPT_CHUNK: int = 10

    # ── 게이티드 진단 (메인 우선 → 오답 시 하위 파고들기) ──────────
    # 진단 시작 시 '메인(최상위)' 개념만 출제하고, 하위(선수) 개념은 잠금.
    # 메인을 '맞히면' 그 하위 선수지식은 안다고 보고 출제 생략(자동 확정).
    # 메인을 '틀리면' 그 개념의 직접 하위(선수)만 잠금 해제해 결손을 확인.
    BKT_GATED_MODE: bool = True
    # 한 개념당 출제 문항 수(게이티드 모드). 1이면 1문항으로 판정 → 문항 최소화.
    BKT_GATED_QUESTIONS_PER_CONCEPT: int = 1
    # 오답 시 파고드는 최대 단계. 1 = 메인의 직접 하위까지만 ('최대한 한 단계').
    BKT_GATED_MAX_DESCENT: int = 1

    # ── 그래프 전파(Graph Propagation) ────────────────────────────
    # 정답 시: 선수 개념(prerequisites)을 이미 안다는 증거 → p 상향 전파
    # 오답 시: 후속 개념(dependents)을 모른다는 증거 → p 하향 전파
    # DECAY: 거리 1-hop마다 전파 강도가 줄어드는 감쇠율 (0~1).
    #   예) DECAY=0.5이면 직접 선수는 100%, 그 선수의 선수는 50%, ... 감쇠.
    BKT_PROPAGATION_DECAY: float = 0.5
    # 전파로 갱신된 p가 확정 경계를 넘어도, 실제로 문항을 풀지 않은 개념은
    # '간접 확정'으로 표시 — 이후 남은 문항 타겟에서 제외.
    BKT_PROPAGATION_MIN_QUESTIONS: int = 1  # 최소 이 수 이상 직접 풀어야 직접 확정

    # ── 적응형 라우팅 / JIT 커리큘럼 ──────────────────────────────
    # 진단 숙련도(p_known)가 이 값 이상이면 '점수 높음' → 메인 브릿지 100%,
    # 미만이면 '점수 낮음' → 약한 선수개념 + 메인 브릿지로 스캐폴딩.
    LEARNING_HIGH_THRESHOLD: float = 0.50
    # 점수 낮음일 때의 구성비 (선수 40% + 메인 60%).
    LEARNING_PREREQ_RATIO: float = 0.40
    LEARNING_MAIN_RATIO: float = 0.60

    # CORS (프론트 dev 서버)
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]


settings = Settings()
