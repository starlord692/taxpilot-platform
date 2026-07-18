"""OCR provider interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal


@dataclass(frozen=True)
class OCRExtraction:
    """OCR provider extraction output."""

    raw_text: str
    language: str | None
    confidence_score: Decimal
    processing_time_ms: int


class OCRProvider(ABC):
    """Pluggable OCR provider contract."""

    provider_name: str

    @abstractmethod
    async def extract_text(self, content: bytes, *, language: str | None) -> str:
        """Extract raw text from document bytes."""

    @abstractmethod
    async def detect_language(self, text: str) -> str | None:
        """Detect extracted text language."""

    @abstractmethod
    async def get_confidence(self, text: str) -> Decimal:
        """Return OCR confidence score."""

    async def process(
        self,
        content: bytes,
        *,
        language: str | None,
    ) -> OCRExtraction:
        """Run the provider extraction pipeline."""
        started_at = datetime.now(tz=UTC)
        raw_text = await self.extract_text(content, language=language)
        detected_language = language or await self.detect_language(raw_text)
        confidence = await self.get_confidence(raw_text)
        elapsed = datetime.now(tz=UTC) - started_at
        return OCRExtraction(
            raw_text=raw_text,
            language=detected_language,
            confidence_score=confidence,
            processing_time_ms=max(int(elapsed.total_seconds() * 1000), 1),
        )
