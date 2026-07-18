"""Document review events."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.common.events import Event
from app.common.models.abstract.timestamp import utc_now


@dataclass(frozen=True)
class ValidationCompletedEvent(Event):
    """Event published when business validation completes."""

    document_id: uuid.UUID
    business_id: uuid.UUID
    issue_count: int
    event_name: str = "document.validation_completed"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class ReviewApprovedEvent(Event):
    """Event published when a document review is approved."""

    document_id: uuid.UUID
    business_id: uuid.UUID
    reviewed_by: uuid.UUID
    event_name: str = "document.review_approved"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class ReviewRejectedEvent(Event):
    """Event published when a document review is rejected."""

    document_id: uuid.UUID
    business_id: uuid.UUID
    reviewed_by: uuid.UUID
    event_name: str = "document.review_rejected"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class CorrectionRequestedEvent(Event):
    """Event published when review requests correction."""

    document_id: uuid.UUID
    business_id: uuid.UUID
    reviewed_by: uuid.UUID
    event_name: str = "document.correction_requested"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class DocumentReadyForAutomationEvent(Event):
    """Event published when document is ready for automation."""

    document_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "document.ready_for_automation"
    occurred_at: datetime = field(default_factory=utc_now)
