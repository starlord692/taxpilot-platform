"""Reusable sales schema validators."""

import re
from datetime import date
from decimal import Decimal

from app.modules.identity.validators import normalize_and_validate_email

CUSTOMER_NAME_MIN_LENGTH = 2
CUSTOMER_NAME_MAX_LENGTH = 150
PHONE_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
GSTIN_PATTERN = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"
)
PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
TWO_DECIMAL_PLACES = Decimal("0.01")
MAX_DECIMAL_EXPONENT = -2


def validate_customer_name(value: str) -> str:
    """Validate and normalize a customer name."""
    normalized = _normalize_spaces(value)
    if len(normalized) < CUSTOMER_NAME_MIN_LENGTH:
        raise ValueError("customer name must be at least 2 characters")
    if len(normalized) > CUSTOMER_NAME_MAX_LENGTH:
        raise ValueError("customer name must be at most 150 characters")
    return normalized


def validate_email(value: str | None) -> str | None:
    """Validate and normalize an optional customer email address."""
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


def validate_positive_decimal(value: Decimal, *, field_name: str) -> Decimal:
    """Validate a positive decimal amount."""
    normalized = validate_decimal_precision(value, field_name=field_name)
    if normalized <= Decimal("0.00"):
        raise ValueError(f"{field_name} must be greater than zero")
    return normalized


def validate_non_negative_decimal(value: Decimal, *, field_name: str) -> Decimal:
    """Validate a non-negative decimal amount."""
    normalized = validate_decimal_precision(value, field_name=field_name)
    if normalized < Decimal("0.00"):
        raise ValueError(f"{field_name} must be zero or greater")
    return normalized


def validate_decimal_precision(value: Decimal, *, field_name: str) -> Decimal:
    """Validate a decimal value has at most two fractional digits."""
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and exponent < MAX_DECIMAL_EXPONENT:
        raise ValueError(f"{field_name} must have at most 2 decimal places")
    return value.quantize(TWO_DECIMAL_PLACES)


def validate_invoice_dates(
    *,
    invoice_date: date | None,
    due_date: date | None,
) -> None:
    """Validate invoice due date is not before invoice date."""
    if invoice_date is not None and due_date is not None and due_date < invoice_date:
        raise ValueError("due_date must be on or after invoice_date")


def _normalize_spaces(value: str) -> str:
    """Trim a string and collapse internal whitespace."""
    return " ".join(value.strip().split())
