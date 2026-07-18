"""Vendor lifecycle events."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.common.events import Event
from app.common.models.abstract.timestamp import utc_now


@dataclass(frozen=True)
class VendorCreatedEvent(Event):
    """Event published after a vendor is created."""

    vendor_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "vendor.created"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class VendorUpdatedEvent(Event):
    """Event published after a vendor is updated."""

    vendor_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "vendor.updated"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class VendorDeactivatedEvent(Event):
    """Event published after a vendor is deactivated."""

    vendor_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "vendor.deactivated"
    occurred_at: datetime = field(default_factory=utc_now)
