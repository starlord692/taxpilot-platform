"""Shared extraction value objects."""

from dataclasses import dataclass
from decimal import Decimal

from app.modules.documents.extraction.models import ExtractedFieldSource


@dataclass(frozen=True)
class ExtractedValue:
    """Transient extracted field value."""

    field_name: str
    field_value: str
    confidence: Decimal
    source: ExtractedFieldSource
    page_number: int = 1
