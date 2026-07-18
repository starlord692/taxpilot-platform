"""Reusable Inventory schema validators."""

from decimal import Decimal

MONEY_DECIMAL_PLACES = Decimal("0.01")
QUANTITY_DECIMAL_PLACES = Decimal("0.0001")
MAX_MONEY_EXPONENT = -2
MAX_QUANTITY_EXPONENT = -4


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


def validate_non_negative_decimal(
    value: Decimal,
    *,
    field_name: str,
    places: Decimal = MONEY_DECIMAL_PLACES,
    max_exponent: int = MAX_MONEY_EXPONENT,
) -> Decimal:
    """Validate a non-negative decimal value."""
    normalized = validate_decimal_precision(
        value,
        field_name=field_name,
        places=places,
        max_exponent=max_exponent,
    )
    if normalized < Decimal("0"):
        raise ValueError(f"{field_name} must be zero or greater")
    return normalized


def validate_positive_decimal(
    value: Decimal,
    *,
    field_name: str,
    places: Decimal = QUANTITY_DECIMAL_PLACES,
    max_exponent: int = MAX_QUANTITY_EXPONENT,
) -> Decimal:
    """Validate a positive decimal value."""
    normalized = validate_decimal_precision(
        value,
        field_name=field_name,
        places=places,
        max_exponent=max_exponent,
    )
    if normalized <= Decimal("0"):
        raise ValueError(f"{field_name} must be greater than zero")
    return normalized


def validate_decimal_precision(
    value: Decimal,
    *,
    field_name: str,
    places: Decimal,
    max_exponent: int,
) -> Decimal:
    """Validate decimal precision and normalize scale."""
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and exponent < max_exponent:
        decimal_places = abs(max_exponent)
        raise ValueError(
            f"{field_name} must have at most {decimal_places} decimal places"
        )
    return value.quantize(places)


def _normalize_spaces(value: str) -> str:
    """Trim a string and collapse internal whitespace."""
    return " ".join(value.strip().split())
