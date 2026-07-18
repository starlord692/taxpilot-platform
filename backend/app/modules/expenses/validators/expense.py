"""Reusable expense schema validators."""

from decimal import Decimal

TWO_DECIMAL_PLACES = Decimal("0.01")
MAX_DECIMAL_EXPONENT = -2


def validate_required_text(
    value: str,
    *,
    field_name: str,
    max_length: int,
) -> str:
    """Validate and normalize required text."""
    normalized = _normalize_spaces(value)
    if not normalized:
        raise ValueError(f"{field_name} is required")
    if len(normalized) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters")
    return normalized


def validate_optional_text(
    value: str | None,
    *,
    field_name: str,
    max_length: int,
) -> str | None:
    """Validate and normalize optional text."""
    if value is None:
        return None
    normalized = _normalize_spaces(value)
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters")
    return normalized


def validate_positive_decimal(value: Decimal, *, field_name: str) -> Decimal:
    """Validate a positive decimal value."""
    normalized = validate_decimal_precision(value, field_name=field_name)
    if normalized <= Decimal("0.00"):
        raise ValueError(f"{field_name} must be greater than zero")
    return normalized


def validate_non_negative_decimal(value: Decimal, *, field_name: str) -> Decimal:
    """Validate a non-negative decimal value."""
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


def validate_attachment_count(value: int) -> int:
    """Validate attachment count is not negative."""
    if value < 0:
        raise ValueError("attachment_count must be zero or greater")
    return value


def validate_expense_total(
    *,
    subtotal: Decimal | None,
    tax_amount: Decimal | None,
    total_amount: Decimal | None,
) -> None:
    """Validate total amount equals subtotal plus tax when all are supplied."""
    if subtotal is None or tax_amount is None or total_amount is None:
        return
    if total_amount != subtotal + tax_amount:
        raise ValueError("total_amount must equal subtotal plus tax_amount")


def _normalize_spaces(value: str) -> str:
    """Trim a string and collapse internal whitespace."""
    return " ".join(value.strip().split())
