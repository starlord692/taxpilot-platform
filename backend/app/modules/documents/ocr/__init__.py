"""OCR provider exports."""

from app.modules.documents.ocr.factory import OCRProviderFactory
from app.modules.documents.ocr.interface import OCRExtraction, OCRProvider
from app.modules.documents.ocr.providers import EasyOCRProvider, TesseractOCRProvider

__all__ = [
    "EasyOCRProvider",
    "OCRExtraction",
    "OCRProvider",
    "OCRProviderFactory",
    "TesseractOCRProvider",
]
