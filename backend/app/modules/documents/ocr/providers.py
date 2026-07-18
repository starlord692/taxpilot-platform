"""Built-in OCR provider implementations."""

import asyncio
import importlib
import io
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

from app.modules.documents.exceptions import OCRProcessingException
from app.modules.documents.ocr.interface import OCRExtraction, OCRProvider

PDF_SIGNATURE = b"%PDF"
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_PAGES = 10
EASYOCR_TEXT_INDEX = 1
EASYOCR_CONFIDENCE_INDEX = 2
EASYOCR_MIN_TEXT_RESULT_LENGTH = 2
EASYOCR_MIN_CONFIDENCE_RESULT_LENGTH = 3


class TesseractOCRProvider(OCRProvider):
    """Tesseract OCR provider using pytesseract, Pillow, and pdf2image."""

    provider_name = "tesseract"

    def __init__(
        self,
        *,
        languages: Sequence[str] | None = None,
        tesseract_path: str | None = None,
        max_pages: int = DEFAULT_MAX_PAGES,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """Initialize provider configuration."""
        self._languages = list(languages or ["eng"])
        self._tesseract_path = tesseract_path
        self._max_pages = max_pages
        self._timeout_seconds = timeout_seconds
        self._last_confidence = Decimal("0.00")

    async def process(
        self,
        content: bytes,
        *,
        language: str | None,
    ) -> OCRExtraction:
        """Run OCR with timing, confidence, and timeout handling."""
        started_at = datetime.now(tz=UTC)
        try:
            raw_text, confidence = await asyncio.wait_for(
                asyncio.to_thread(self._extract_sync, content, language),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise OCRProcessingException("OCR processing timed out") from exc
        except OCRProcessingException:
            raise
        except Exception as exc:
            raise OCRProcessingException(
                "Tesseract OCR provider failed",
                details={"reason": str(exc)},
            ) from exc
        elapsed = datetime.now(tz=UTC) - started_at
        return OCRExtraction(
            raw_text=raw_text,
            language=language or await self.detect_language(raw_text),
            confidence_score=confidence,
            processing_time_ms=max(int(elapsed.total_seconds() * 1000), 1),
        )

    async def extract_text(self, content: bytes, *, language: str | None) -> str:
        """Extract text from image or PDF bytes."""
        raw_text, confidence = await asyncio.to_thread(
            self._extract_sync,
            content,
            language,
        )
        self._last_confidence = confidence
        return raw_text

    async def detect_language(self, text: str) -> str | None:
        """Return configured language when text was extracted."""
        if not text:
            return None
        return "+".join(self._languages)

    async def get_confidence(self, text: str) -> Decimal:
        """Return the most recent OCR confidence score."""
        if not text:
            return Decimal("0.00")
        return self._last_confidence

    def _extract_sync(
        self,
        content: bytes,
        language: str | None,
    ) -> tuple[str, Decimal]:
        """Run Tesseract synchronously for images or PDFs."""
        pytesseract = self._import_module("pytesseract")
        if self._tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = self._tesseract_path
        pages = (
            self._pdf_pages(content)
            if content.startswith(PDF_SIGNATURE)
            else [self._image(content)]
        )
        lang = language or "+".join(self._languages)
        text_parts: list[str] = []
        confidences: list[Decimal] = []
        for page in pages[: self._max_pages]:
            text_parts.append(str(pytesseract.image_to_string(page, lang=lang)))
            data = pytesseract.image_to_data(
                page,
                lang=lang,
                output_type=pytesseract.Output.DICT,
            )
            confidences.extend(self._parse_confidences(data.get("conf", [])))
        confidence = self._average(confidences)
        raw_text = "\n".join(part.strip() for part in text_parts if part.strip())
        return raw_text, confidence

    def _pdf_pages(self, content: bytes) -> list[Any]:
        """Convert PDF bytes to page images."""
        pdf2image = self._import_module("pdf2image")
        try:
            return list(
                pdf2image.convert_from_bytes(
                    content,
                    first_page=1,
                    last_page=self._max_pages,
                )
            )
        except Exception as exc:
            raise OCRProcessingException(
                "Unable to convert PDF for OCR",
                details={"reason": str(exc)},
            ) from exc

    def _image(self, content: bytes) -> Any:
        """Open image bytes with Pillow."""
        pillow_image = self._import_module("PIL.Image")
        try:
            image = pillow_image.open(io.BytesIO(content))
            image.load()
            return image
        except Exception as exc:
            raise OCRProcessingException(
                "Unsupported or corrupt image",
                details={"reason": str(exc)},
            ) from exc

    def _parse_confidences(self, values: Sequence[Any]) -> list[Decimal]:
        """Parse Tesseract confidence values."""
        confidences: list[Decimal] = []
        for value in values:
            try:
                confidence = Decimal(str(value))
            except Exception:
                continue
            if confidence >= 0:
                confidences.append(confidence)
        return confidences

    def _average(self, values: Sequence[Decimal]) -> Decimal:
        """Return average confidence."""
        if not values:
            return Decimal("0.00")
        return (sum(values) / Decimal(len(values))).quantize(Decimal("0.01"))

    def _import_module(self, module_name: str) -> Any:
        """Import dependency and wrap missing-engine failures."""
        try:
            return cast(Any, importlib.import_module(module_name))
        except ImportError as exc:
            raise OCRProcessingException(
                "OCR dependency is not installed",
                details={"dependency": module_name},
            ) from exc


class EasyOCRProvider(OCRProvider):
    """EasyOCR provider for image OCR."""

    provider_name = "easyocr"

    def __init__(
        self,
        *,
        languages: Sequence[str] | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """Initialize provider configuration."""
        self._languages = list(languages or ["en"])
        self._timeout_seconds = timeout_seconds
        self._reader: Any | None = None
        self._last_confidence = Decimal("0.00")

    async def process(
        self,
        content: bytes,
        *,
        language: str | None,
    ) -> OCRExtraction:
        """Run EasyOCR with timing, confidence, and timeout handling."""
        started_at = datetime.now(tz=UTC)
        try:
            raw_text, confidence = await asyncio.wait_for(
                asyncio.to_thread(self._extract_sync, content, language),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise OCRProcessingException("OCR processing timed out") from exc
        except OCRProcessingException:
            raise
        except Exception as exc:
            raise OCRProcessingException(
                "EasyOCR provider failed",
                details={"reason": str(exc)},
            ) from exc
        elapsed = datetime.now(tz=UTC) - started_at
        return OCRExtraction(
            raw_text=raw_text,
            language=language or await self.detect_language(raw_text),
            confidence_score=confidence,
            processing_time_ms=max(int(elapsed.total_seconds() * 1000), 1),
        )

    async def extract_text(self, content: bytes, *, language: str | None) -> str:
        """Extract text from image bytes."""
        raw_text, confidence = await asyncio.to_thread(
            self._extract_sync,
            content,
            language,
        )
        self._last_confidence = confidence
        return raw_text

    async def detect_language(self, text: str) -> str | None:
        """Return configured language when text was extracted."""
        if not text:
            return None
        return ",".join(self._languages)

    async def get_confidence(self, text: str) -> Decimal:
        """Return the most recent OCR confidence score."""
        if not text:
            return Decimal("0.00")
        return self._last_confidence

    def _extract_sync(
        self,
        content: bytes,
        language: str | None,
    ) -> tuple[str, Decimal]:
        """Run EasyOCR synchronously for image bytes."""
        if content.startswith(PDF_SIGNATURE):
            raise OCRProcessingException("EasyOCR provider does not support PDF input")
        image = self._image_array(content)
        reader = self._get_reader(language)
        raw_results = reader.readtext(image)
        text_parts: list[str] = []
        confidences: list[Decimal] = []
        for result in raw_results:
            if len(result) >= EASYOCR_MIN_TEXT_RESULT_LENGTH:
                text_parts.append(str(result[EASYOCR_TEXT_INDEX]))
            if len(result) >= EASYOCR_MIN_CONFIDENCE_RESULT_LENGTH:
                confidences.append(
                    Decimal(str(result[EASYOCR_CONFIDENCE_INDEX])) * Decimal("100")
                )
        confidence = self._average(confidences)
        return "\n".join(text_parts).strip(), confidence

    def _get_reader(self, language: str | None) -> Any:
        """Return cached EasyOCR reader."""
        easyocr = self._import_module("easyocr")
        languages = [language] if language else self._languages
        if self._reader is None:
            self._reader = easyocr.Reader(languages, gpu=False)
        return self._reader

    def _image_array(self, content: bytes) -> Any:
        """Open image bytes and return a numpy array for EasyOCR."""
        pillow_image = self._import_module("PIL.Image")
        numpy = self._import_module("numpy")
        try:
            image = pillow_image.open(io.BytesIO(content)).convert("RGB")
            return numpy.array(image)
        except Exception as exc:
            raise OCRProcessingException(
                "Unsupported or corrupt image",
                details={"reason": str(exc)},
            ) from exc

    def _average(self, values: Sequence[Decimal]) -> Decimal:
        """Return average confidence."""
        if not values:
            return Decimal("0.00")
        return (sum(values) / Decimal(len(values))).quantize(Decimal("0.01"))

    def _import_module(self, module_name: str) -> Any:
        """Import dependency and wrap missing-engine failures."""
        try:
            return cast(Any, importlib.import_module(module_name))
        except ImportError as exc:
            raise OCRProcessingException(
                "OCR dependency is not installed",
                details={"dependency": module_name},
            ) from exc
