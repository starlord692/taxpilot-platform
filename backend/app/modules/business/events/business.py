"""Business lifecycle events."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.common.events import Event
from app.common.models.abstract.timestamp import utc_now


@dataclass(frozen=True)
class BusinessCreatedEvent(Event):
    """Event published after a business is created."""

    business_id: uuid.UUID
    owner_user_id: uuid.UUID
    event_name: str = "business.created"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class BusinessUpdatedEvent(Event):
    """Event published after a business is updated."""

    business_id: uuid.UUID
    event_name: str = "business.updated"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class BusinessArchivedEvent(Event):
    """Event published after a business is archived."""

    business_id: uuid.UUID
    event_name: str = "business.archived"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class BusinessRestoredEvent(Event):
    """Event published after a business is restored."""

    business_id: uuid.UUID
    event_name: str = "business.restored"
    occurred_at: datetime = field(default_factory=utc_now)
