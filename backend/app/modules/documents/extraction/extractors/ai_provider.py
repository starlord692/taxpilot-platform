"""AI-assisted extraction provider interface and mock implementation."""

from abc import ABC, abstractmethod
from decimal import Decimal

from app.modules.documents.extraction.extractors.types import ExtractedValue
from app.modules.documents.extraction.models import ExtractedFieldSource
from app.modules.documents.models import DocumentType


class AIExtractionProvider(ABC):
    """Provider contract for AI-assisted extraction."""

    @abstractmethod
    async def extract(
        self,
        *,
        text: str,
        document_type: DocumentType,
    ) -> list[ExtractedValue]:
        """Extract fields from text."""

    @abstractmethod
    async def explain(self, field_name: str) -> str:
        """Explain a field extraction."""

    @abstractmethod
    async def confidence(self, field_name: str, field_value: str) -> Decimal:
        """Return confidence for a field."""


class MockAIProvider(AIExtractionProvider):
    """Deterministic AI provider used until external LLMs are introduced."""

    async def extract(
        self,
        *,
        text: str,
        document_type: DocumentType,
    ) -> list[ExtractedValue]:
        """Extract a small set of fields from contextual cues."""
        _ = document_type
        fields: list[ExtractedValue] = []
        if "supplier gstin" in text.lower():
            fields.append(
                ExtractedValue(
                    field_name="supplier_gstin",
                    field_value=self._after_label(text, "Supplier GSTIN"),
                    confidence=Decimal("84.00"),
                    source=ExtractedFieldSource.AI,
                )
            )
        if "customer gstin" in text.lower():
            fields.append(
                ExtractedValue(
                    field_name="customer_gstin",
                    field_value=self._after_label(text, "Customer GSTIN"),
                    confidence=Decimal("84.00"),
                    source=ExtractedFieldSource.AI,
                )
            )
        return [field for field in fields if field.field_value]

    async def explain(self, field_name: str) -> str:
        """Return deterministic explanation."""
        return f"Mock AI matched contextual label for {field_name}."

    async def confidence(self, field_name: str, field_value: str) -> Decimal:
        """Return deterministic confidence."""
        _ = field_name
        return Decimal("84.00") if field_value else Decimal("0.00")

    def _after_label(self, text: str, label: str) -> str:
        """Return value after a label on the same line."""
        for line in text.splitlines():
            normalized_line = line.strip()
            if normalized_line.lower().startswith(label.lower()):
                return (
                    normalized_line.split(":", maxsplit=1)[-1]
                    .strip()
                    .split()[0]
                    .upper()
                )
        return ""
