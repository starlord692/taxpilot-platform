"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import ClassVar, Literal, Self
from urllib.parse import urlparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "testing", "staging", "production"]

DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://taxpilot:taxpilot@localhost:5432/taxpilot"
)
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
MIN_PRODUCTION_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Runtime settings for the TaxPilot AI backend."""

    production_secret_placeholders: ClassVar[set[str]] = {
        "",
        "change-me",
        "changeme",
        "secret",
        "test-secret-key",
        "replace-with-a-secure-random-secret",
    }
    valid_log_levels: ClassVar[set[str]] = {
        "CRITICAL",
        "ERROR",
        "WARNING",
        "INFO",
        "DEBUG",
    }
    valid_ocr_providers: ClassVar[set[str]] = {"tesseract", "easyocr"}

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

    @field_validator("api_v1_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        """Ensure API prefixes are absolute paths."""
        if not value.startswith("/"):
            raise ValueError("API_V1_PREFIX must start with '/'")
        return value.rstrip("/") or "/"

    @field_validator(
        "database_pool_size",
        "document_max_upload_size_bytes",
        "max_ocr_pages",
        "ocr_timeout",
    )
    @classmethod
    def validate_positive_integer(cls, value: int) -> int:
        """Ensure size and duration settings are positive."""
        if value <= 0:
            raise ValueError("Configuration value must be greater than zero")
        return value

    @field_validator("database_max_overflow")
    @classmethod
    def validate_non_negative_integer(cls, value: int) -> int:
        """Ensure overflow capacity is not negative."""
        if value < 0:
            raise ValueError("DATABASE_MAX_OVERFLOW must be zero or greater")
        return value

    @field_validator("ocr_provider")
    @classmethod
    def validate_ocr_provider(cls, value: str) -> str:
        """Normalize and validate configured OCR provider."""
        normalized = value.strip().lower()
        if normalized not in cls.valid_ocr_providers:
            raise ValueError("OCR_PROVIDER must be one of: easyocr, tesseract")
        return normalized

    @field_validator("ocr_languages")
    @classmethod
    def validate_ocr_languages(cls, value: str) -> str:
        """Ensure at least one OCR language is configured."""
        languages = [language.strip() for language in value.split(",")]
        if not any(languages):
            raise ValueError("OCR_LANGUAGES must include at least one language")
        return ",".join(language for language in languages if language)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Normalize and validate logging level."""
        normalized = value.strip().upper()
        if normalized not in cls.valid_log_levels:
            raise ValueError(
                "LOG_LEVEL must be one of: CRITICAL, ERROR, WARNING, INFO, DEBUG"
            )
        return normalized

    @model_validator(mode="after")
    def validate_production_safety(self) -> Self:
        """Fail fast when production settings contain unsafe defaults."""
        if self.environment != "production":
            return self

        if self.debug:
            raise ValueError("DEBUG must be false in production")
        self._validate_production_secret()
        self._validate_production_token_lifetimes()
        self._validate_production_database_url()
        self._validate_production_redis_url()
        return self

    def _validate_production_secret(self) -> None:
        """Reject missing, placeholder, or weak production token secrets."""
        secret = self.identity_token_secret_key.strip()
        if secret.lower() in self.production_secret_placeholders:
            raise ValueError("IDENTITY_TOKEN_SECRET_KEY must be configured")
        if len(secret) < MIN_PRODUCTION_SECRET_LENGTH:
            raise ValueError(
                "IDENTITY_TOKEN_SECRET_KEY must be at least "
                f"{MIN_PRODUCTION_SECRET_LENGTH} characters in production"
            )

    def _validate_production_token_lifetimes(self) -> None:
        """Reject unusable token lifetimes in production."""
        if self.identity_access_token_expire_minutes <= 0:
            raise ValueError(
                "IDENTITY_ACCESS_TOKEN_EXPIRE_MINUTES must be greater than zero "
                "in production"
            )
        if self.identity_refresh_token_expire_days <= 0:
            raise ValueError(
                "IDENTITY_REFRESH_TOKEN_EXPIRE_DAYS must be greater than zero "
                "in production"
            )

    def _validate_production_database_url(self) -> None:
        """Reject missing database credentials and known development defaults."""
        if self.database_url == DEFAULT_DATABASE_URL:
            raise ValueError("DATABASE_URL must not use the development default")

        parsed = urlparse(self.database_url)
        if not parsed.scheme or not parsed.hostname:
            raise ValueError("DATABASE_URL must be a valid database URL")
        if not parsed.username or not parsed.password:
            raise ValueError("DATABASE_URL must include production credentials")
        if parsed.username == "taxpilot" and parsed.password == "taxpilot":
            raise ValueError("DATABASE_URL must not use default credentials")

    def _validate_production_redis_url(self) -> None:
        """Reject missing Redis credentials and known development defaults."""
        if self.redis_url == DEFAULT_REDIS_URL:
            raise ValueError("REDIS_URL must not use the development default")

        parsed = urlparse(self.redis_url)
        if not parsed.scheme or not parsed.hostname:
            raise ValueError("REDIS_URL must be a valid Redis URL")
        if parsed.password is None:
            raise ValueError("REDIS_URL must include production credentials")


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
