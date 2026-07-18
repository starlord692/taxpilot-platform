"""Validation helpers for extracted document fields."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from app.modules.documents.extraction.extractors.types import ExtractedValue

GSTIN_PATTERN = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$",
    re.IGNORECASE,
)
PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$", re.IGNORECASE)
DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y")
LOW_CONFIDENCE_THRESHOLD = Decimal("70.00")


@dataclass(frozen=True)
class ValidationResult:
    """Extraction validation result."""

    fields: list[ExtractedValue]
    issues: list[str]
    review_required: bool
    overall_confidence: Decimal


class ExtractionFieldValidator:
    """Validate extracted fields and calculate confidence."""

    def validate(self, fields: list[ExtractedValue]) -> ValidationResult:
        """Validate extracted fields."""
        issues: list[str] = []
        field_names: set[str] = set()
        duplicates: set[str] = set()
        for field in fields:
            if field.field_name in field_names:
                duplicates.add(field.field_name)
            field_names.add(field.field_name)
            self._validate_field(field, issues)
        for duplicate in sorted(duplicates):
            issues.append(f"duplicate field: {duplicate}")
        self._validate_totals(fields, issues)
        missing = self._missing_mandatory_fields(fields)
        issues.extend(f"missing mandatory field: {field}" for field in missing)
        overall_confidence = self._overall_confidence(fields)
        review_required = bool(issues) or overall_confidence < LOW_CONFIDENCE_THRESHOLD
        return ValidationResult(
            fields=fields,
            issues=issues,
            review_required=review_required,
            overall_confidence=overall_confidence,
        )

    def _validate_field(self, field: ExtractedValue, issues: list[str]) -> None:
        """Validate one field."""
        if (
            field.field_name.endswith("gstin") or field.field_name == "gstin"
        ) and not GSTIN_PATTERN.fullmatch(field.field_value):
            issues.append(f"invalid GSTIN: {field.field_value}")
        if field.field_name == "pan" and not PAN_PATTERN.fullmatch(
            field.field_value
        ):
            issues.append(f"invalid PAN: {field.field_value}")
        if field.field_name in {
            "invoice_date",
            "due_date",
            "date",
        } and self._parse_date(field.field_value) is None:
            issues.append(f"invalid date: {field.field_value}")

    def _validate_totals(
        self,
        fields: list[ExtractedValue],
        issues: list[str],
    ) -> None:
        """Validate tax and grand total consistency when enough fields exist."""
        values = self._field_values(fields)
        subtotal = values.get("subtotal")
        discount = values.get("discount", Decimal("0.00"))
        taxes = sum(
            values.get(field_name, Decimal("0.00"))
            for field_name in ("cgst", "sgst", "igst", "cess")
        )
        grand_total = values.get("grand_total")
        round_off = values.get("round_off", Decimal("0.00"))
        if subtotal is None or grand_total is None:
            return
        expected = subtotal - discount + taxes + round_off
        if abs(expected - grand_total) > Decimal("1.00"):
            issues.append("grand total does not match subtotal, tax, and round off")

    def _missing_mandatory_fields(self, fields: list[ExtractedValue]) -> list[str]:
        """Return missing mandatory invoice fields."""
        names = {field.field_name for field in fields}
        mandatory = {"invoice_number", "grand_total"}
        return sorted(mandatory - names)

    def _overall_confidence(self, fields: list[ExtractedValue]) -> Decimal:
        """Calculate average confidence."""
        if not fields:
            return Decimal("0.00")
        return (
            sum(field.confidence for field in fields) / Decimal(len(fields))
        ).quantize(Decimal("0.01"))

    def _field_values(self, fields: list[ExtractedValue]) -> dict[str, Decimal]:
        """Return decimal values for amount fields."""
        values: dict[str, Decimal] = {}
        for field in fields:
            try:
                values[field.field_name] = Decimal(field.field_value)
            except Exception:
                continue
        return values

    def _parse_date(self, value: str) -> date | None:
        """Parse common OCR date formats."""
        for date_format in DATE_FORMATS:
            try:
                return datetime.strptime(value, date_format).date()
            except ValueError:
                continue
        return None
