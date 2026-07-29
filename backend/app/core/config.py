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
    # 기본 생성 모델 — 하드코딩 대신 여기서 관리(materials·learning·review·seed
    # 전 기능이 공유). 호출측이 model= kwarg로 개별 override 가능.
    SOLAR_MODEL: str = "solar-pro3"

    # CORS (프론트 dev 서버)
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]


settings = Settings()
