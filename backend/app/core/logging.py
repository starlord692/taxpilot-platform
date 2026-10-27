"""Structured logging configuration."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings, mask_connection_string

SENSITIVE_LOG_PATTERNS: tuple[str, ...] = (
    "password",
    "secret",
    "token",
    "authorization",
    "identity_token_secret_key",
    "database_url",
    "redis_url",
    "credentials",
    "api_key",
)


def sanitize_log_value(key: str, value: Any) -> Any:
    """Sanitize individual log record attributes if key is sensitive."""
    key_lower = key.lower()
    if any(pattern in key_lower for pattern in SENSITIVE_LOG_PATTERNS):
        if isinstance(value, str) and ("//" in value and "@" in value):
            return mask_connection_string(value)
        return "[REDACTED]"
    if isinstance(value, dict):
        return {k: sanitize_log_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_log_value(key, item) for item in value]
    return value


class JsonFormatter(logging.Formatter):
    """Format log records as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Return a JSON-formatted log record."""
        message = record.getMessage()
        payload: dict[str, Any] = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        reserved = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)
        for key, value in record.__dict__.items():
            if key not in reserved and key not in {"message", "asctime"}:
                payload[key] = sanitize_log_value(key, value)

        return json.dumps(payload, default=str)


def configure_logging(settings: Settings) -> None:
    """Configure root logging for the application."""
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(settings.log_level.upper())

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)
