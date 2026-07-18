"""Document extraction events."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.common.events import Event
from app.common.models.abstract.timestamp import utc_now


@dataclass(frozen=True)
class ExtractionCompletedEvent(Event):
    """Event published when structured extraction completes."""

    document_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "document.extraction_completed"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class ExtractionFailedEvent(Event):
    """Event published when structured extraction fails."""

    document_id: uuid.UUID
    business_id: uuid.UUID
    reason: str
    event_name: str = "document.extraction_failed"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class ReviewRequiredEvent(Event):
    """Event published when extraction needs manual review."""

    document_id: uuid.UUID
    business_id: uuid.UUID
    reason: str
    event_name: str = "document.extraction_review_required"
    occurred_at: datetime = field(default_factory=utc_now)
