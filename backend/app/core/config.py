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

    # 교차 검증용 EXAONE (OpenAI 호환 엔드포인트 — 키가 있으면 검증 모델로 사용)
    EXAONE_API_KEY: str = ""
    EXAONE_BASE_URL: str = "https://api.friendli.ai/serverless/v1"
    EXAONE_MODEL: str = "LGAI-EXAONE/K-EXAONE-236B-A23B"

    # CORS (프론트 dev 서버)
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]


settings = Settings()
