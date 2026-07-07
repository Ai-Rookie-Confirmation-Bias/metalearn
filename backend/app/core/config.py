"""전역 환경 설정: .env / 환경변수 파싱 (pydantic-settings)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # DB (compose의 environment에서 주입)
    DATABASE_URL: str = "postgresql+psycopg://postgres:dev@db:5432/metalearn"
    # false: 시드·튜터 등 앱 데이터는 메모리만 사용 (PostgreSQL 미기록)
    PERSIST_TO_DB: bool = False

    # 인증
    SECRET_KEY: str = "change-me-in-env"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # Upstage Solar (메인 LLM)
    UPSTAGE_API_KEY: str = ""
    SOLAR_BASE_URL: str = "https://api.upstage.ai/v1"
    SOLAR_MODEL: str = "solar-pro3"
    SOLAR_EMBED_QUERY_MODEL: str = "embedding-query"
    SOLAR_EMBED_PASSAGE_MODEL: str = "embedding-passage"
    UPSTAGE_PARSE_MODEL: str = "document-parse"
    SOLAR_CHAT_MODEL: str = "solar-pro3"
    SOLAR_EMBED_MODEL: str = "embedding-query"
    SOLAR_EMBED_DIM: int = 4096
    # 주의: "document-parse" 별칭은 최신 출시보다 늦게 갱신됨(2026-07-03
    # 실호출 확인: 별칭→260128) → 최신 버전을 명시 고정. 새 버전 출시 시 갱신.
    DOCUMENT_PARSE_MODEL: str = "document-parse-260630"

    # 개념 추출 깊이 상한.
    # 명세의 "N-2 깊이 제한" — 문서 목차 깊이(N)보다 2단계 얕게 파편화해
    # 과분할/노이즈를 막는다. 추출 스키마(재귀 ConceptNode)에서 강제.
    MAX_CONCEPT_DEPTH: int = 2

    # ── 개념 추출: 섹션 분할 + 커버리지 (ISSUE-008) ───────────────
    # 전체 문서 단일 호출은 출력 토큰 한계로 ~20개 압축·누락이 생겨,
    # 마크다운 헤딩 기준 섹션(청크)별로 나눠 호출한다.
    # 청크 최대 문자 수. 청크 ≈ 진단 섹션 단위이기도 하므로 너무 크면 섹션이
    # 과하게 넓어져(파트급) 게이팅이 관대해진다. 4000자 ≈ 중주제 크기.
    EXTRACTION_SECTION_CHAR_BUDGET: int = 4000
    EXTRACTION_MAX_CONCURRENCY: int = 3  # 섹션 추출 LLM 동시 호출 수
    # 임베딩 배치 크기 (ISSUE-010): 개념당 1호출 → N개씩 묶어 호출 수 절감.
    EMBED_BATCH_SIZE: int = 64
    # 임베딩 코사인 유사도가 이 값 이상이면 같은 개념으로 병합
    # (예: "데이터베이스" vs "데이터베이스 (DBMS)"). embed는 어차피 개념마다
    # 수행하므로 추가 비용 없음.
    CONCEPT_DEDUP_SIM_THRESHOLD: float = 0.92

    # ── 일괄 dedup 패스 (ISSUE-011) ──────────────────────────────
    # 실측: 진짜 중복이 0.85~0.92 구간에 분포하고 같은 구간에 별개 개념도
    # 밀집(단일 문턱으로 분리 불가) → 유사도는 후보 수집만, 판정은 LLM이.
    DEDUP_CANDIDATE_SIM_THRESHOLD: float = 0.85
    DEDUP_MAX_PAIRS: int = 200        # 코스당 후보쌍 상한 (프롬프트 폭주 방지)
    DEDUP_JUDGE_BATCH_SIZE: int = 50  # LLM 판정 1회당 쌍 수

    # ── 조건부 섹션 계층 (ISSUE-009) ──────────────────────────────
    # 한 청크의 타겟 개념이 이 수 이상이면 섹션 대표 개념을 depth 0 노드로
    # 만들고 타겟들을 그 하위(kind='contains')로 내린다 → 진단 메인 수 억제.
    # 미달(논문 등 소형 문서)이면 섹션 노드 없이 타겟이 그대로 메인
    # → 기존 동작과 동일하게 우아하게 퇴화.
    SECTION_NODE_MIN_FANOUT: int = 8
    # 섹션 문항 오답 시 하위(contains) 용어 중 잠금 해제해 실제 출제할 대표 수.
    # 나머지 하위는 오답 신호를 하향 전파만 받고 잠금 유지(학습 중 정밀화 대상).
    BKT_GATED_CONTAINS_SAMPLE: int = 3

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

    # ── 진단 스코핑 (팀 회의 2026-07-05: "가벼운 기반지식 체크, 문항 최소화") ──
    # 회의 결정 구현 제안 — 진단은 parsing 팀원 담당 영역, parsing 리뷰 대상.
    # 진단의 목적 = ① 시작점(floor) 찾기 ② 학습 전 기반지식 결손 확인.
    # → '커리큘럼 앞부분 이해도 + 선행 기반지식 체크'이지 문서 전체 훑기가
    #   아니다: 초반 메인 개념 + 그 선수 방향(depth_level 큰 쪽 = 더 기초)
    #   개념만 가볍게 체크하고, 문서 뒷부분 개념은 출제하지 않는다
    #   (시작점 판정에 불필요 — ceiling은 기본 문서 끝).
    # 대형 문서(예: 수학 코스 개념 191개)는 메인만으로도 수십 문항이 되어
    # '가벼운 계단식 체크' 취지를 벗어난다 → 아래 노브로 강제 제한.
    #
    # 시작 시 진단 타겟 개념 총 상한. 메인이 이 수 이하인 소형 코스는
    # 기존처럼 메인 전원 출제로 퇴화한다.
    DIAG_MAX_MAIN_CONCEPTS: int = 6
    # 상한 중 선수 방향(기반지식) 프록시에 배정할 개수 — 초반 메인들의 직접
    # 선수 중 depth_level 큰(더 기초) 순. 나머지 몫은 커리큘럼 초반 메인
    # 순서대로 채우며, 선수 엣지가 없으면 초반 메인으로 대신 채운다.
    DIAG_PREREQ_PROBE_COUNT: int = 2
    # 세션 총 문항 하드캡 (오답 시 하위 하강 문항 포함). 캡 도달 시 남은
    # 미확정 개념은 그래프 전파/사전값(P_INIT)으로 마무리하고 세션 done 처리.
    DIAG_MAX_TOTAL_QUESTIONS: int = 10

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

    # 업로드 PDF 저장 경로 (컨테이너 내부)
    UPLOAD_DIR: str = "/app/uploads"

    @property
    def llm_provider(self) -> str:
        if self.UPSTAGE_API_KEY.strip():
            return "solar"
        return "mock"

    @property
    def llm_provider_label(self) -> str:
        return "Solar" if self.llm_provider == "solar" else "Mock"

    @property
    def use_mock_ai(self) -> bool:
        return self.llm_provider == "mock"


settings = Settings()
