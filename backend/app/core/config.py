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
    SOLAR_MODEL: str = "solar-pro2"
    SOLAR_EMBED_QUERY_MODEL: str = "embedding-query"
    SOLAR_EMBED_PASSAGE_MODEL: str = "embedding-passage"
    UPSTAGE_PARSE_MODEL: str = "document-parse"

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
