"""Document processing events."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.common.events import Event
from app.common.models.abstract.timestamp import utc_now


@dataclass(frozen=True)
class DocumentUploadedEvent(Event):
    """Event published when a document is uploaded."""

    document_id: uuid.UUID
    business_id: uuid.UUID
    uploaded_by: uuid.UUID
    event_name: str = "document.uploaded"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class OCRStartedEvent(Event):
    """Event published when OCR starts."""

    document_id: uuid.UUID
    business_id: uuid.UUID
    provider: str
    event_name: str = "document.ocr_started"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class OCRCompletedEvent(Event):
    """Event published when OCR completes."""

    document_id: uuid.UUID
    business_id: uuid.UUID
    provider: str
    event_name: str = "document.ocr_completed"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class OCRFailedEvent(Event):
    """Event published when OCR fails."""

    document_id: uuid.UUID
    business_id: uuid.UUID
    provider: str
    reason: str
    event_name: str = "document.ocr_failed"
    occurred_at: datetime = field(default_factory=utc_now)
