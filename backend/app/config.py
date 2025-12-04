# backend/app/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import AnyUrl


class Settings(BaseSettings):
    # 기본 설정
    app_name: str = "PoliStep"
    debug: bool = True

    # DB
    database_url: AnyUrl | str = "sqlite:///./polistep.db"

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 1 day

    # LLM / API keys
    google_api_key: str | None = None  # Gemini용
    openai_api_key: str | None = None

    # 파일 / 다운로드 경로
    download_dir: str = "./data/downloads"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
