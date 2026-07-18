"""Supplier lifecycle events."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.common.events import Event
from app.common.models.abstract.timestamp import utc_now


@dataclass(frozen=True)
class SupplierCreatedEvent(Event):
    """Event published after a supplier is created."""

    supplier_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "supplier.created"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class SupplierUpdatedEvent(Event):
    """Event published after a supplier is updated."""

    supplier_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "supplier.updated"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class SupplierDeactivatedEvent(Event):
    """Event published after a supplier is deactivated."""

    supplier_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "supplier.deactivated"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class SupplierReactivatedEvent(Event):
    """Event published after a supplier is reactivated."""

    supplier_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "supplier.reactivated"
    occurred_at: datetime = field(default_factory=utc_now)
