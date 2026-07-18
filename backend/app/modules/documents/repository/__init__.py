"""Document repository exports."""

from app.modules.documents.repository.document import (
    DocumentPageRepository,
    DocumentRepository,
    OCRResultRepository,
)

__all__ = [
    "DocumentPageRepository",
    "DocumentRepository",
    "OCRResultRepository",
]
