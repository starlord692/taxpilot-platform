"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Any, Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "testing", "staging", "production"]
UNSECURE_DEFAULT_SECRET = "replace-with-a-secure-random-secret"
MIN_SECRET_LENGTH = 32


def mask_connection_string(url: str) -> str:
    """Mask embedded passwords in database or redis connection strings."""
    if "@" not in url or "://" not in url:
        return url
    try:
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            user_pass, host_part = rest.split("@", 1)
            if ":" in user_pass:
                user = user_pass.split(":", 1)[0]
                return f"{scheme}://{user}:[REDACTED]@{host_part}"
    except Exception:
        pass
    return url


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
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

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

    outbox_relay_enabled: bool = False
    outbox_relay_poll_interval_seconds: float = 1.0
    outbox_relay_batch_size: int = 50

    @model_validator(mode="before")
    @classmethod
    def set_environment_defaults(cls, data: Any) -> Any:
        """Ensure staging/production do not inherit dev CORS origins."""
        if isinstance(data, dict):
            env = data.get("environment", "development")
            cors_raw = data.get("cors_origins")
            if isinstance(cors_raw, str):
                cors_str = cors_raw.strip()
                if cors_str.startswith("[") and cors_str.endswith("]"):
                    import json
                    try:
                        data["cors_origins"] = json.loads(cors_str)
                    except Exception:
                        data["cors_origins"] = [c.strip().strip('"').strip("'") for c in cors_str[1:-1].split(",") if c.strip()]
                else:
                    data["cors_origins"] = [c.strip() for c in cors_str.split(",") if c.strip()]
            elif env in ("production", "staging") and "cors_origins" not in data:
                data["cors_origins"] = []
        return data

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        """Enforce strict secret and CORS requirements in staging/production."""
        if self.environment in ("production", "staging"):
            secret = self.identity_token_secret_key
            if (
                not secret
                or secret == UNSECURE_DEFAULT_SECRET
                or len(secret) < MIN_SECRET_LENGTH
            ):
                raise ValueError(
                    f"identity_token_secret_key must be configured with a secure key "
                    f"(at least {MIN_SECRET_LENGTH} chars) in {self.environment}"
                )
            for origin in self.cors_origins:
                origin_lower = origin.lower()
                if "localhost" in origin_lower or "127.0.0.1" in origin_lower:
                    raise ValueError(
                        f"cors_origins in {self.environment} environment cannot "
                        f"contain development origin '{origin}'"
                    )
        return self

    def get_redacted_dict(self) -> dict[str, Any]:
        """Return a dictionary representation with sensitive fields redacted."""
        data = self.model_dump()
        if data.get("identity_token_secret_key"):
            data["identity_token_secret_key"] = "[REDACTED]"
        if data.get("database_url"):
            data["database_url"] = mask_connection_string(data["database_url"])
        if data.get("redis_url"):
            data["redis_url"] = mask_connection_string(data["redis_url"])
        return data

    def __repr__(self) -> str:
        """Return a safe string representation without raw secrets."""
        fields = ", ".join(f"{k}={v!r}" for k, v in self.get_redacted_dict().items())
        return f"Settings({fields})"

    def __str__(self) -> str:
        """Return string representation matching __repr__."""
        return self.__repr__()


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
