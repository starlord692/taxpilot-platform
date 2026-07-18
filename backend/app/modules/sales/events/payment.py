"""Sales payment lifecycle events."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.common.events import Event
from app.common.models.abstract.timestamp import utc_now


@dataclass(frozen=True)
class PaymentRecordedEvent(Event):
    """Event published after a payment is recorded."""

    payment_id: uuid.UUID
    invoice_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "payment.recorded"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class PaymentUpdatedEvent(Event):
    """Event published after a payment is updated."""

    payment_id: uuid.UUID
    invoice_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "payment.updated"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class PaymentDeletedEvent(Event):
    """Event published after a payment is deleted."""

    payment_id: uuid.UUID
    invoice_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "payment.deleted"
    occurred_at: datetime = field(default_factory=utc_now)
