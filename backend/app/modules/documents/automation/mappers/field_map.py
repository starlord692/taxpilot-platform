"""Extracted field mapping helpers."""

import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.modules.documents.automation.exceptions import AutomationMappingException
from app.modules.documents.extraction.models import ExtractedDocument

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y")


class ExtractedFieldMap:
    """Convenience lookup for reviewed extracted fields."""

    def __init__(self, extracted_document: ExtractedDocument) -> None:
        """Build the map from an extracted document."""
        values: dict[str, list[str]] = {}
        for field in extracted_document.fields:
            values.setdefault(field.field_name, []).append(field.field_value)
        self._values = values

    def first(self, field_name: str) -> str | None:
        """Return the latest value for a field."""
        values = self._values.get(field_name, [])
        return values[-1] if values else None

    def required(self, field_name: str) -> str:
        """Return required field value or raise."""
        value = self.first(field_name)
        if value is None or not value.strip():
            raise AutomationMappingException(
                "Required extracted field is missing",
                details={"field_name": field_name},
            )
        return value.strip()

    def uuid(self, field_name: str, *, required: bool = True) -> uuid.UUID | None:
        """Return a UUID field value."""
        value = self.required(field_name) if required else self.first(field_name)
        if value is None:
            return None
        try:
            return uuid.UUID(value)
        except ValueError as exc:
            raise AutomationMappingException(
                "Extracted field is not a valid UUID",
                details={"field_name": field_name, "value": value},
            ) from exc

    def decimal(
        self,
        field_name: str,
        *,
        default: Decimal | None = None,
    ) -> Decimal:
        """Return a decimal field value."""
        value = self.first(field_name)
        if value is None:
            if default is not None:
                return default
            raise AutomationMappingException(
                "Required decimal field is missing",
                details={"field_name": field_name},
            )
        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise AutomationMappingException(
                "Extracted field is not a valid decimal",
                details={"field_name": field_name, "value": value},
            ) from exc

    def date(self, field_name: str, *, required: bool = True) -> date | None:
        """Return a date field value."""
        value = self.required(field_name) if required else self.first(field_name)
        if value is None:
            return None
        for date_format in DATE_FORMATS:
            try:
                return datetime.strptime(value, date_format).date()
            except ValueError:
                continue
        raise AutomationMappingException(
            "Extracted field is not a supported date",
            details={"field_name": field_name, "value": value},
        )
