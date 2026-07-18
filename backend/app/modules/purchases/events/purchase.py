"""Purchase invoice lifecycle events."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.common.events import Event
from app.common.models.abstract.timestamp import utc_now


@dataclass(frozen=True)
class PurchaseCreatedEvent(Event):
    """Event published after a purchase invoice is created."""

    purchase_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "purchase.created"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class PurchaseUpdatedEvent(Event):
    """Event published after a purchase invoice is updated."""

    purchase_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "purchase.updated"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class PurchaseApprovedEvent(Event):
    """Event published after a purchase invoice is approved."""

    purchase_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "purchase.approved"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class PurchaseReceivedEvent(Event):
    """Event published after a purchase invoice is marked received."""

    purchase_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "purchase.received"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class PurchasePaidEvent(Event):
    """Event published after a purchase invoice is marked paid."""

    purchase_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "purchase.paid"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class PurchaseCancelledEvent(Event):
    """Event published after a purchase invoice is cancelled."""

    purchase_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "purchase.cancelled"
    occurred_at: datetime = field(default_factory=utc_now)
