"""Document event exports."""

from app.modules.documents.events.document import (
    DocumentUploadedEvent,
    OCRCompletedEvent,
    OCRFailedEvent,
    OCRStartedEvent,
)

__all__ = [
    "DocumentUploadedEvent",
    "OCRCompletedEvent",
    "OCRFailedEvent",
    "OCRStartedEvent",
]
