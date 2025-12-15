from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyUrl, Field


class Settings(BaseSettings):
    # pydantic-settings v2 설정
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # .env에 있어도 모델에 없는 값들은 무시
    )

    # --- 앱 기본 정보 ---
    app_name: str = "POLYSTEP_backend"

    # --- DB ---
    database_url: AnyUrl  # .env의 database_url 사용

    # --- JWT / Auth ---
    # .env에 있는 jwt_secret_key 값을 secret_key로 매핑
    secret_key: str = Field(alias="jwt_secret_key")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 1 day

    # --- LLM / 외부 API ---
    google_api_key: str | None = None  # GOOGLE_API_KEY 또는 google_api_key
    openai_api_key: str | None = None  # 필요시 사용

    # browser-use용 키 (.env에 browser_use_api_key 이미 있음)
    browser_use_api_key: str | None = None

    # --- 기타 ---
    # .env에 download_dir가 있으면 이 값으로, 없으면 기본값 사용
    download_dir: str = "./data/downloads"

    # 프론트엔드 CORS 허용 origin
    frontend_origin: str | None = "http://localhost:5173"


settings = Settings()
