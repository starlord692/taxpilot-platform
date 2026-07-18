"""Tests for real OCR provider adapters."""

import importlib
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from app.modules.documents.exceptions import OCRProcessingException
from app.modules.documents.ocr import OCRProviderFactory
from app.modules.documents.ocr.providers import EasyOCRProvider, TesseractOCRProvider


class FakeImage:
    """Tiny fake Pillow image."""

    def __init__(self, name: str = "image") -> None:
        """Initialize fake image."""
        self.name = name

    def load(self) -> None:
        """Pretend to load image bytes."""

    def convert(self, mode: str) -> "FakeImage":
        """Pretend to convert image mode."""
        _ = mode
        return self


def patch_tesseract_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    image_failure: bool = False,
    pdf_failure: bool = False,
) -> None:
    """Patch OCR dependencies used by Tesseract provider."""
    original_import = importlib.import_module

    def fake_import(module_name: str) -> Any:
        if module_name == "pytesseract":
            return SimpleNamespace(
                pytesseract=SimpleNamespace(tesseract_cmd=""),
                Output=SimpleNamespace(DICT="dict"),
                image_to_string=lambda image, lang: f"text-{image.name}-{lang}",
                image_to_data=lambda image, lang, output_type: {
                    "conf": ["90", "80", "-1"]
                },
            )
        if module_name == "pdf2image":
            if pdf_failure:
                return SimpleNamespace(
                    convert_from_bytes=lambda *args, **kwargs: (
                        _ for _ in ()
                    ).throw(RuntimeError("bad pdf"))
                )
            return SimpleNamespace(
                convert_from_bytes=lambda *args, **kwargs: [
                    FakeImage("page1"),
                    FakeImage("page2"),
                ]
            )
        if module_name == "PIL.Image":
            if image_failure:
                return SimpleNamespace(
                    open=lambda _content: (_ for _ in ()).throw(
                        RuntimeError("bad image")
                    ),
                )
            return SimpleNamespace(open=lambda _content: FakeImage())
        return original_import(module_name)

    monkeypatch.setattr(importlib, "import_module", fake_import)


def patch_easyocr_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch OCR dependencies used by EasyOCR provider."""
    original_import = importlib.import_module

    class FakeReader:
        """Fake EasyOCR reader."""

        def __init__(self, languages: list[str], *, gpu: bool) -> None:
            """Initialize reader."""
            self.languages = languages
            self.gpu = gpu

        def readtext(self, image: object) -> list[tuple[object, str, float]]:
            """Return fake OCR results."""
            _ = image
            return [(object(), "hello", 0.8), (object(), "world", 0.9)]

    def fake_import(module_name: str) -> Any:
        if module_name == "easyocr":
            return SimpleNamespace(Reader=FakeReader)
        if module_name == "PIL.Image":
            return SimpleNamespace(open=lambda _content: FakeImage())
        if module_name == "numpy":
            return SimpleNamespace(array=lambda image: image)
        return original_import(module_name)

    monkeypatch.setattr(importlib, "import_module", fake_import)


@pytest.mark.asyncio
async def test_tesseract_image_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tesseract provider extracts image text and confidence."""
    patch_tesseract_dependencies(monkeypatch)
    provider = TesseractOCRProvider(languages=["eng"], tesseract_path="/usr/bin/tess")

    result = await provider.process(b"image-bytes", language=None)

    assert "text-image-eng" in result.raw_text
    assert result.confidence_score == Decimal("85.00")
    assert result.language == "eng"
    assert result.processing_time_ms >= 1


@pytest.mark.asyncio
async def test_tesseract_multi_page_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tesseract provider extracts multi-page PDF text."""
    patch_tesseract_dependencies(monkeypatch)
    provider = TesseractOCRProvider(languages=["eng"], max_pages=2)

    result = await provider.process(b"%PDF fake", language="eng")

    assert "text-page1-eng" in result.raw_text
    assert "text-page2-eng" in result.raw_text
    assert result.confidence_score == Decimal("85.00")


@pytest.mark.asyncio
async def test_easyocr_image_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    """EasyOCR provider extracts image text and confidence."""
    patch_easyocr_dependencies(monkeypatch)
    provider = EasyOCRProvider(languages=["en"])

    result = await provider.process(b"image-bytes", language=None)

    assert result.raw_text == "hello\nworld"
    assert result.confidence_score == Decimal("85.00")
    assert result.language == "en"


def test_ocr_factory_uses_configured_default_provider() -> None:
    """Factory resolves default provider from configuration."""
    factory = OCRProviderFactory(default_provider="easyocr", languages=["eng"])

    provider = factory.get("default")

    assert isinstance(provider, EasyOCRProvider)


@pytest.mark.asyncio
async def test_missing_ocr_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing OCR dependencies are wrapped in provider exceptions."""
    original_import = importlib.import_module

    def fake_import(module_name: str) -> Any:
        if module_name == "pytesseract":
            raise ImportError("missing")
        return original_import(module_name)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    provider = TesseractOCRProvider()

    with pytest.raises(OCRProcessingException):
        await provider.process(b"image-bytes", language=None)


@pytest.mark.asyncio
async def test_unsupported_image_and_corrupt_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unsupported image and corrupt PDF inputs are handled gracefully."""
    patch_tesseract_dependencies(monkeypatch, image_failure=True)
    provider = TesseractOCRProvider()

    with pytest.raises(OCRProcessingException):
        await provider.process(b"bad-image", language=None)

    patch_tesseract_dependencies(monkeypatch, pdf_failure=True)
    with pytest.raises(OCRProcessingException):
        await provider.process(b"%PDF bad", language=None)


@pytest.mark.asyncio
async def test_easyocr_rejects_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    """EasyOCR provider rejects PDF input because it supports images only."""
    patch_easyocr_dependencies(monkeypatch)
    provider = EasyOCRProvider()

    with pytest.raises(OCRProcessingException):
        await provider.process(b"%PDF fake", language=None)
