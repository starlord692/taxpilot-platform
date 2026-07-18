"""Document model exports."""

from app.modules.documents.models.document import Document
from app.modules.documents.models.enums import DocumentType, ExtractionStatus
from app.modules.documents.models.ocr_result import OCRResult
from app.modules.documents.models.page import DocumentPage

__all__ = [
    "Document",
    "DocumentPage",
    "DocumentType",
    "ExtractionStatus",
    "OCRResult",
]
