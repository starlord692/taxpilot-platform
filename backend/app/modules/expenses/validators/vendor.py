"""Reusable vendor schema validators."""

import re

from app.modules.identity.validators import normalize_and_validate_email

VENDOR_NAME_MIN_LENGTH = 2
VENDOR_NAME_MAX_LENGTH = 150
ADDRESS_MAX_LENGTH = 1000
PHONE_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
GSTIN_PATTERN = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"
)
PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


def validate_vendor_name(value: str) -> str:
    """Validate and normalize a vendor name."""
    normalized = _normalize_spaces(value)
    if len(normalized) < VENDOR_NAME_MIN_LENGTH:
        raise ValueError("vendor name must be at least 2 characters")
    if len(normalized) > VENDOR_NAME_MAX_LENGTH:
        raise ValueError("vendor name must be at most 150 characters")
    return normalized


def validate_email(value: str | None) -> str | None:
    """Validate and normalize an optional vendor email address."""
    if value is None:
        return None
    return normalize_and_validate_email(value)


def validate_phone(value: str | None) -> str | None:
    """Validate an optional E.164 phone number."""
    if value is None:
        return None
    normalized = value.strip()
    if PHONE_PATTERN.fullmatch(normalized) is None:
        raise ValueError("phone must use E.164 format, e.g. +919876543210")
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


def validate_address(value: str | None) -> str | None:
    """Validate and normalize an optional vendor address."""
    if value is None:
        return None
    normalized = _normalize_spaces(value)
    if not normalized:
        return None
    if len(normalized) > ADDRESS_MAX_LENGTH:
        raise ValueError("address must be at most 1000 characters")
    return normalized


def _normalize_spaces(value: str) -> str:
    """Trim a string and collapse internal whitespace."""
    return " ".join(value.strip().split())
