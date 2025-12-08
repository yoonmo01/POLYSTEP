# backend/app/config.py
from functools import lru_cache

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 🔧 pydantic-settings v2 설정
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ✅ .env에 정의 안 된 값이 있어도 에러 안 나게
    )

    # 기본 설정
    app_name: str = "PoliStep"
    debug: bool = True

    # DB
    # 예시: postgresql+psycopg2://user:password@localhost:5432/polistep
    database_url: AnyUrl | str = Field(..., alias="DATABASE_URL")

    # JWT
    jwt_secret_key: str = Field(..., alias="JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 1 day

    # LLM / API keys
    # GOOGLE_API_KEY, OPENAI_API_KEY 그대로 읽어오게 alias 설정
    google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")

    # 🔹 browser-use Cloud API 키 (선택)
    # .env 에서 BROWSER_USE_API_KEY 로 읽어옴
    browser_use_api_key: str | None = Field(
        default=None,
        alias="BROWSER_USE_API_KEY",
    )

    # 파일 / 다운로드 경로
    download_dir: str = Field(default="./data/downloads", alias="DOWNLOAD_DIR")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
