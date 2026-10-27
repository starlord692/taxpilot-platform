"""Tests for configuration safety and secret redaction."""

import json
import logging

import pytest

from app.core.config import Settings, mask_connection_string
from app.core.logging import JsonFormatter


def test_default_settings_development() -> None:
    """Settings load cleanly with development defaults."""
    settings = Settings(environment="development")
    assert settings.environment == "development"
    assert settings.app_name == "TaxPilot AI"
    assert settings.outbox_relay_enabled is False


def test_production_environment_rejects_empty_secret() -> None:
    """Production environment requires identity_token_secret_key."""
    with pytest.raises(
        ValueError, match="identity_token_secret_key must be configured"
    ):
        Settings(environment="production", identity_token_secret_key="")


def test_production_environment_rejects_unsecure_default_secret() -> None:
    """Production environment rejects default placeholder secret."""
    with pytest.raises(
        ValueError, match="identity_token_secret_key must be configured"
    ):
        Settings(
            environment="production",
            identity_token_secret_key="replace-with-a-secure-random-secret",
        )


def test_production_environment_rejects_short_secret() -> None:
    """Production environment rejects secrets shorter than 32 characters."""
    with pytest.raises(
        ValueError, match="identity_token_secret_key must be configured"
    ):
        Settings(
            environment="production",
            identity_token_secret_key="short-secret-key",
        )


def test_staging_environment_requires_secure_secret() -> None:
    """Staging environment enforces strict secret key validation."""
    with pytest.raises(
        ValueError, match="identity_token_secret_key must be configured"
    ):
        Settings(
            environment="staging",
            identity_token_secret_key="replace-with-a-secure-random-secret",
        )


def test_production_environment_accepts_valid_secret() -> None:
    """Production environment accepts a valid secret of sufficient length."""
    secure_key = "a" * 32
    settings = Settings(
        environment="production",
        identity_token_secret_key=secure_key,
    )
    assert settings.identity_token_secret_key == secure_key


def test_mask_connection_string() -> None:
    """mask_connection_string redacts embedded credentials."""
    raw_db_url = "postgresql+asyncpg://taxpilot_user:super_secret_pass@localhost:5432/taxpilot_db"
    masked = mask_connection_string(raw_db_url)
    assert "super_secret_pass" not in masked
    assert (
        masked
        == "postgresql+asyncpg://taxpilot_user:[REDACTED]@localhost:5432/taxpilot_db"
    )

    plain_url = "postgresql+asyncpg://localhost:5432/taxpilot_db"
    assert mask_connection_string(plain_url) == plain_url


def test_redacted_dict_and_repr() -> None:
    """Settings dict and repr mask sensitive credentials."""
    settings = Settings(
        identity_token_secret_key="my-secret-jwt-key-for-testing-only",
        database_url="postgresql+asyncpg://admin:dbpassword123@dbhost:5432/appdb",
    )

    redacted = settings.get_redacted_dict()
    assert redacted["identity_token_secret_key"] == "[REDACTED]"
    assert "dbpassword123" not in redacted["database_url"]
    assert (
        redacted["database_url"]
        == "postgresql+asyncpg://admin:[REDACTED]@dbhost:5432/appdb"
    )

    repr_str = repr(settings)
    assert "my-secret-jwt-key-for-testing-only" not in repr_str
    assert "dbpassword123" not in repr_str
    assert "[REDACTED]" in repr_str


def test_json_formatter_sanitizes_sensitive_extra_fields() -> None:
    """JsonFormatter redacts sensitive extra log attributes."""
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="User authentication attempt",
        args=(),
        exc_info=None,
    )
    record.password = "UserSecretPassword123!"  # type: ignore[attr-defined]
    record.database_url = "postgresql+asyncpg://user:secretpass@localhost:5432/db"  # type: ignore[attr-defined]
    record.safe_field = "Public Information"  # type: ignore[attr-defined]

    formatted_log = formatter.format(record)
    parsed = json.loads(formatted_log)

    assert "UserSecretPassword123!" not in formatted_log
    assert "secretpass" not in formatted_log
    assert parsed["password"] == "[REDACTED]"
    assert (
        parsed["database_url"]
        == "postgresql+asyncpg://user:[REDACTED]@localhost:5432/db"
    )
    assert parsed["safe_field"] == "Public Information"


def test_production_environment_defaults_to_empty_cors_origins() -> None:
    """Production environment does not inherit development CORS origins."""
    settings = Settings(
        environment="production",
        identity_token_secret_key="a" * 32,
    )
    assert settings.cors_origins == []


def test_production_environment_rejects_localhost_cors_origin() -> None:
    """Production environment rejects localhost and loopback CORS origins."""
    with pytest.raises(ValueError, match="cannot contain development origin"):
        Settings(
            environment="production",
            identity_token_secret_key="a" * 32,
            cors_origins=["http://localhost:3000"],
        )


def test_production_environment_accepts_secure_cors_origin() -> None:
    """Production environment accepts explicit non-development origins."""
    prod_origin = "https://app.taxpilot.ai"
    settings = Settings(
        environment="production",
        identity_token_secret_key="a" * 32,
        cors_origins=[prod_origin],
    )
    assert settings.cors_origins == [prod_origin]
