"""Document schema exports."""

from app.modules.documents.schemas.documents import (
    DocumentListResponse,
    DocumentPageResponse,
    DocumentResponse,
    DocumentUploadRequest,
    OCRProcessRequest,
    OCRResultResponse,
)

__all__ = [
    "DocumentListResponse",
    "DocumentPageResponse",
    "DocumentResponse",
    "DocumentUploadRequest",
    "OCRProcessRequest",
    "OCRResultResponse",
]
