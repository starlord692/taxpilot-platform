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

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
