"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "testing", "staging", "production"]


class Settings(BaseSettings):
    """Runtime settings for the TaxPilot AI backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "TaxPilot AI"
    app_version: str = "1.0.0"
    environment: Environment = "development"
    debug: bool = False

    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://taxpilot:taxpilot@localhost:5432/taxpilot"
    database_echo: bool = False
    database_pool_size: int = 5
    database_max_overflow: int = 10

    redis_url: str = "redis://localhost:6379/0"

    identity_token_secret_key: str = ""
    identity_access_token_expire_minutes: int = 15
    identity_refresh_token_expire_days: int = 30

    document_storage_path: str = "storage/documents"
    document_max_upload_size_bytes: int = 10 * 1024 * 1024
    ocr_provider: str = "tesseract"
    ocr_languages: str = "eng"
    tesseract_path: str | None = None
    max_ocr_pages: int = 10
    ocr_timeout: int = 60

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
