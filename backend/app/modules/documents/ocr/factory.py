"""OCR provider factory."""

from app.modules.documents.exceptions import OCRProviderNotFoundException
from app.modules.documents.ocr.interface import OCRProvider
from app.modules.documents.ocr.providers import EasyOCRProvider, TesseractOCRProvider

DEFAULT_PROVIDER_MARKERS = {"default", "configured", "auto"}


class OCRProviderFactory:
    """Resolve configured OCR providers by name."""

    def __init__(
        self,
        *,
        default_provider: str = "tesseract",
        languages: list[str] | None = None,
        tesseract_path: str | None = None,
        max_pages: int = 10,
        timeout_seconds: int = 60,
    ) -> None:
        """Initialize provider registry."""
        normalized_languages = languages or ["eng"]
        self._default_provider = default_provider.lower()
        self._providers: dict[str, OCRProvider] = {
            TesseractOCRProvider.provider_name: TesseractOCRProvider(
                languages=normalized_languages,
                tesseract_path=tesseract_path,
                max_pages=max_pages,
                timeout_seconds=timeout_seconds,
            ),
            EasyOCRProvider.provider_name: EasyOCRProvider(
                languages=self._easyocr_languages(normalized_languages),
                timeout_seconds=timeout_seconds,
            ),
        }

    def get(self, provider_name: str) -> OCRProvider:
        """Return OCR provider by name."""
        normalized_provider = provider_name.lower()
        if normalized_provider in DEFAULT_PROVIDER_MARKERS:
            normalized_provider = self._default_provider
        provider = self._providers.get(normalized_provider)
        if provider is None:
            raise OCRProviderNotFoundException(
                "OCR provider is not configured",
                details={"provider": provider_name},
            )
        return provider

    def _easyocr_languages(self, languages: list[str]) -> list[str]:
        """Normalize common Tesseract language codes for EasyOCR."""
        language_map = {"eng": "en", "hin": "hi"}
        return [language_map.get(language, language) for language in languages]
