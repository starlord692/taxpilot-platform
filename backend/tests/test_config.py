"""Configuration validation and production safety tests."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import DEFAULT_DATABASE_URL, DEFAULT_REDIS_URL, Settings

PRODUCTION_SECRET = "s" * 32
PRODUCTION_DATABASE_URL = (
    "postgresql+asyncpg://taxpilot_app:secure-db-password@db:5432/taxpilot"
)
PRODUCTION_REDIS_URL = "redis://:secure-redis-password@redis:6379/0"


def build_production_settings(
    *,
    identity_token_secret_key: str = PRODUCTION_SECRET,
    identity_access_token_expire_minutes: int = 15,
    identity_refresh_token_expire_days: int = 30,
    database_url: str = PRODUCTION_DATABASE_URL,
    redis_url: str = PRODUCTION_REDIS_URL,
    debug: bool = False,
) -> Settings:
    """Build production settings with secure defaults for tests."""
    return Settings(
        environment="production",
        debug=debug,
        identity_token_secret_key=identity_token_secret_key,
        identity_access_token_expire_minutes=identity_access_token_expire_minutes,
        identity_refresh_token_expire_days=identity_refresh_token_expire_days,
        database_url=database_url,
        redis_url=redis_url,
    )


def assert_settings_error(
    message: str,
    exc_info: pytest.ExceptionInfo[ValidationError],
) -> None:
    """Assert a configuration validation error contains actionable text."""
    assert message in str(exc_info.value)


def test_development_defaults_remain_simple() -> None:
    """Development keeps local defaults for a low-friction setup."""
    settings = Settings()

    assert settings.environment == "development"
    assert settings.database_url == DEFAULT_DATABASE_URL
    assert settings.redis_url == DEFAULT_REDIS_URL
    assert settings.ocr_provider == "tesseract"
    assert settings.assistant_provider == "mock"
    assert settings.assistant_model == "taxpilot-mock-assistant-v1"
    assert settings.log_level == "INFO"


def test_production_accepts_secure_configuration() -> None:
    """Production starts when required settings are explicit and secure."""
    settings = build_production_settings()

    assert settings.environment == "production"
    assert settings.identity_token_secret_key == PRODUCTION_SECRET
    assert settings.database_url == PRODUCTION_DATABASE_URL
    assert settings.redis_url == PRODUCTION_REDIS_URL


def test_production_rejects_empty_token_secret() -> None:
    """Production refuses to start without a token signing secret."""
    with pytest.raises(ValidationError) as exc_info:
        build_production_settings(identity_token_secret_key="")

    assert_settings_error("IDENTITY_TOKEN_SECRET_KEY must be configured", exc_info)


def test_production_rejects_placeholder_token_secret() -> None:
    """Production refuses documented placeholder secrets."""
    with pytest.raises(ValidationError) as exc_info:
        build_production_settings(
            identity_token_secret_key="replace-with-a-secure-random-secret"
        )

    assert_settings_error("IDENTITY_TOKEN_SECRET_KEY must be configured", exc_info)


def test_production_rejects_short_token_secret() -> None:
    """Production token signing secrets must have enough entropy budget."""
    with pytest.raises(ValidationError) as exc_info:
        build_production_settings(identity_token_secret_key="short-secret")

    assert_settings_error(
        "IDENTITY_TOKEN_SECRET_KEY must be at least 32 characters",
        exc_info,
    )


def test_production_rejects_debug_mode() -> None:
    """Production must not run with debug mode enabled."""
    with pytest.raises(ValidationError) as exc_info:
        build_production_settings(debug=True)

    assert_settings_error("DEBUG must be false in production", exc_info)


def test_production_rejects_non_positive_access_token_lifetime() -> None:
    """Production access token lifetime must be usable."""
    with pytest.raises(ValidationError) as exc_info:
        build_production_settings(identity_access_token_expire_minutes=0)

    assert_settings_error(
        "IDENTITY_ACCESS_TOKEN_EXPIRE_MINUTES must be greater than zero",
        exc_info,
    )


def test_production_rejects_non_positive_refresh_token_lifetime() -> None:
    """Production refresh token lifetime must be usable."""
    with pytest.raises(ValidationError) as exc_info:
        build_production_settings(identity_refresh_token_expire_days=0)

    assert_settings_error(
        "IDENTITY_REFRESH_TOKEN_EXPIRE_DAYS must be greater than zero",
        exc_info,
    )


def test_production_rejects_default_database_url() -> None:
    """Production must not use the development database URL."""
    with pytest.raises(ValidationError) as exc_info:
        build_production_settings(database_url=DEFAULT_DATABASE_URL)

    assert_settings_error(
        "DATABASE_URL must not use the development default",
        exc_info,
    )


def test_production_rejects_database_url_without_credentials() -> None:
    """Production database URLs must include credentials."""
    with pytest.raises(ValidationError) as exc_info:
        build_production_settings(
            database_url="postgresql+asyncpg://db:5432/taxpilot"
        )

    assert_settings_error(
        "DATABASE_URL must include production credentials",
        exc_info,
    )


def test_production_rejects_default_database_credentials() -> None:
    """Production database URLs must not use default credentials."""
    with pytest.raises(ValidationError) as exc_info:
        build_production_settings(
            database_url="postgresql+asyncpg://taxpilot:taxpilot@db:5432/taxpilot"
        )

    assert_settings_error("DATABASE_URL must not use default credentials", exc_info)


def test_production_rejects_default_redis_url() -> None:
    """Production must not use the development Redis URL."""
    with pytest.raises(ValidationError) as exc_info:
        build_production_settings(redis_url=DEFAULT_REDIS_URL)

    assert_settings_error("REDIS_URL must not use the development default", exc_info)


def test_production_rejects_redis_url_without_credentials() -> None:
    """Production Redis URLs must include credentials."""
    with pytest.raises(ValidationError) as exc_info:
        build_production_settings(redis_url="redis://redis:6379/0")

    assert_settings_error("REDIS_URL must include production credentials", exc_info)


def test_ocr_provider_is_validated() -> None:
    """OCR provider typos fail during settings loading."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(ocr_provider="unknown")

    assert_settings_error("OCR_PROVIDER must be one of", exc_info)


def test_assistant_provider_is_validated() -> None:
    """Assistant provider typos fail during settings loading."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(assistant_provider="unknown")

    assert_settings_error("ASSISTANT_PROVIDER must be one of", exc_info)


def test_assistant_model_is_required() -> None:
    """Assistant model must be configured explicitly."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(assistant_model="")

    assert_settings_error("ASSISTANT_MODEL must not be empty", exc_info)


def test_assistant_provider_retries_are_bounded() -> None:
    """Assistant provider retry settings remain bounded."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(assistant_provider_max_retries=4)

    assert_settings_error("ASSISTANT_PROVIDER_MAX_RETRIES must not exceed 3", exc_info)


def test_log_level_is_validated() -> None:
    """Log level typos fail during settings loading."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(log_level="verbose")

    assert_settings_error("LOG_LEVEL must be one of", exc_info)


def test_numeric_configuration_must_be_positive() -> None:
    """Durations, sizes, and limits must be positive."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(ocr_timeout=0)

    assert_settings_error("Configuration value must be greater than zero", exc_info)


def test_env_example_documents_current_settings() -> None:
    """The example env file documents every public backend setting."""
    env_example = Path(__file__).resolve().parents[1] / ".env.example"
    content = env_example.read_text(encoding="utf-8")

    expected_variables = {
        "APP_NAME",
        "APP_VERSION",
        "ENVIRONMENT",
        "DEBUG",
        "API_V1_PREFIX",
        "DATABASE_URL",
        "DATABASE_ECHO",
        "DATABASE_POOL_SIZE",
        "DATABASE_MAX_OVERFLOW",
        "REDIS_URL",
        "IDENTITY_TOKEN_SECRET_KEY",
        "IDENTITY_ACCESS_TOKEN_EXPIRE_MINUTES",
        "IDENTITY_REFRESH_TOKEN_EXPIRE_DAYS",
        "DOCUMENT_STORAGE_PATH",
        "DOCUMENT_MAX_UPLOAD_SIZE_BYTES",
        "OCR_PROVIDER",
        "OCR_LANGUAGES",
        "TESSERACT_PATH",
        "MAX_OCR_PAGES",
        "OCR_TIMEOUT",
        "ASSISTANT_PROVIDER",
        "ASSISTANT_MODEL",
        "ASSISTANT_PROVIDER_TIMEOUT_MS",
        "ASSISTANT_PROVIDER_MAX_RETRIES",
        "ASSISTANT_PROVIDER_FAILOVER_ENABLED",
        "LOG_LEVEL",
    }

    for variable in expected_variables:
        assert f"{variable}=" in content
