"""Reusable business schema validators."""

import re
from datetime import date
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.modules.identity.validators import normalize_and_validate_email

BUSINESS_NAME_MIN_LENGTH = 3
BUSINESS_NAME_MAX_LENGTH = 150
TRADE_NAME_MAX_LENGTH = 150
MEMBERSHIP_ROLE_MAX_LENGTH = 80
PHONE_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
GSTIN_PATTERN = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"
)
PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
LANGUAGE_PATTERN = re.compile(r"^[a-z]{2,3}(?:-[A-Z]{2})?$")
SUPPORTED_URL_SCHEMES = frozenset({"http", "https"})


def validate_business_name(value: str) -> str:
    """Validate and normalize a legal business name."""
    normalized = _normalize_spaces(value)
    if len(normalized) < BUSINESS_NAME_MIN_LENGTH:
        raise ValueError("legal_name must be at least 3 characters")
    if len(normalized) > BUSINESS_NAME_MAX_LENGTH:
        raise ValueError("legal_name must be at most 150 characters")
    return normalized


def validate_trade_name(value: str | None) -> str | None:
    """Validate and normalize an optional trade name."""
    if value is None:
        return None
    normalized = _normalize_spaces(value)
    if not normalized:
        return None
    if len(normalized) > TRADE_NAME_MAX_LENGTH:
        raise ValueError("trade_name must be at most 150 characters")
    return normalized


def validate_business_email(value: str | None) -> str | None:
    """Validate and normalize an optional business email address."""
    if value is None:
        return None
    return normalize_and_validate_email(value)


def validate_business_phone(value: str | None) -> str | None:
    """Validate an optional E.164-compatible phone number."""
    if value is None:
        return None
    normalized = value.strip()
    if PHONE_PATTERN.fullmatch(normalized) is None:
        raise ValueError("business_phone must use E.164 format, e.g. +919876543210")
    return normalized


def validate_website(value: str | None) -> str | None:
    """Validate an optional HTTP or HTTPS website URL."""
    if value is None:
        return None
    normalized = value.strip()
    parsed = urlparse(normalized)
    if parsed.scheme not in SUPPORTED_URL_SCHEMES or not parsed.netloc:
        raise ValueError("website must be a valid HTTP or HTTPS URL")
    return normalized


def validate_gstin(value: str | None) -> str | None:
    """Validate an optional Indian GSTIN."""
    if value is None:
        return None
    normalized = value.strip().upper()
    if not normalized:
        return None
    if GSTIN_PATTERN.fullmatch(normalized) is None:
        raise ValueError("gstin must be a valid Indian GSTIN")
    return normalized


def validate_pan(value: str | None) -> str | None:
    """Validate an optional Indian PAN."""
    if value is None:
        return None
    normalized = value.strip().upper()
    if not normalized:
        return None
    if PAN_PATTERN.fullmatch(normalized) is None:
        raise ValueError("pan must be a valid Indian PAN")
    return normalized


def validate_financial_year_start(value: date) -> date:
    """Validate a financial year start date."""
    return value


def validate_timezone(value: str) -> str:
    """Validate an IANA timezone name."""
    normalized = value.strip()
    try:
        ZoneInfo(normalized)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("timezone must be a valid IANA timezone") from exc
    return normalized


def validate_currency(value: str) -> str:
    """Validate an ISO-4217 currency code shape."""
    normalized = value.strip().upper()
    if CURRENCY_PATTERN.fullmatch(normalized) is None:
        raise ValueError("currency must be a valid ISO-4217 currency code")
    return normalized


def validate_language(value: str) -> str:
    """Validate an ISO language code."""
    normalized = value.strip()
    if LANGUAGE_PATTERN.fullmatch(normalized) is None:
        raise ValueError("language must be a valid ISO language code")
    return normalized


def validate_membership_role(value: str) -> str:
    """Validate a business membership role name."""
    normalized = _normalize_spaces(value).lower()
    if not normalized:
        raise ValueError("role is required")
    if len(normalized) > MEMBERSHIP_ROLE_MAX_LENGTH:
        raise ValueError("role must be at most 80 characters")
    return normalized


def _normalize_spaces(value: str) -> str:
    """Trim a string and collapse internal whitespace."""
    return " ".join(value.strip().split())
