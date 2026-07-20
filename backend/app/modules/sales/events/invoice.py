"""Sales invoice lifecycle events."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.common.events import Event
from app.common.models.abstract.timestamp import utc_now


@dataclass(frozen=True)
class InvoiceCreatedEvent(Event):
    """Event published after an invoice is created."""

    invoice_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "invoice.created"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class InvoiceUpdatedEvent(Event):
    """Event published after an invoice is updated."""

    invoice_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "invoice.updated"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class InvoiceIssuedEvent(Event):
    """Event published after an invoice is issued."""

    invoice_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "invoice.issued"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class InvoiceCancelledEvent(Event):
    """Event published after an invoice is cancelled."""

    invoice_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "invoice.cancelled"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class InvoicePartiallyPaidEvent(Event):
    """Event published after an invoice is marked partially paid."""

    invoice_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "invoice.partially_paid"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class InvoicePaidEvent(Event):
    """Event published after an invoice is marked paid."""

    invoice_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "invoice.paid"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class InvoiceIntelligenceEvaluatedEvent(Event):
    """Advisory event emitted after a read-only invoice evaluation."""

    invoice_id: uuid.UUID
    business_id: uuid.UUID
    recommendation_count: int
    readiness: str
    event_name: str = "invoice.intelligence_evaluated"
    occurred_at: datetime = field(default_factory=utc_now)
