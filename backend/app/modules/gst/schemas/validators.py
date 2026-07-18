"""GST schema validators."""

import re
from datetime import date
from decimal import Decimal

GSTIN_PATTERN = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"
)
HSN_PATTERN = re.compile(r"^\d{4,8}$")
SAC_PATTERN = re.compile(r"^\d{6}$")
MAX_RATE = Decimal("100.00")
MIN_RATE = Decimal("0.00")


def validate_gstin(value: str) -> str:
    """Validate and normalize an Indian GSTIN."""
    normalized = value.strip().upper()
    if GSTIN_PATTERN.fullmatch(normalized) is None:
        raise ValueError("gstin must be a valid Indian GSTIN")
    return normalized


def validate_hsn_code(value: str) -> str:
    """Validate an HSN code."""
    normalized = value.strip()
    if HSN_PATTERN.fullmatch(normalized) is None:
        raise ValueError("HSN code must contain 4 to 8 digits")
    return normalized


def validate_sac_code(value: str) -> str:
    """Validate a SAC code."""
    normalized = value.strip()
    if SAC_PATTERN.fullmatch(normalized) is None:
        raise ValueError("SAC code must contain exactly 6 digits")
    return normalized


def validate_tax_rate(value: Decimal) -> Decimal:
    """Validate a GST rate percentage."""
    if value < MIN_RATE or value > MAX_RATE:
        raise ValueError("GST rates must be between 0 and 100")
    return value


def validate_effective_dates(
    effective_from: date,
    effective_to: date | None,
) -> None:
    """Validate tax rate effective date range."""
    if effective_to is not None and effective_to < effective_from:
        raise ValueError("effective_to must be greater than or equal to effective_from")
