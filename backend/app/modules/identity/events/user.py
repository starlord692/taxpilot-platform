"""Identity user events."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.common.events import Event
from app.common.models.abstract.timestamp import utc_now


@dataclass(frozen=True)
class IdentityUserCreatedEvent(Event):
    """Event published after an identity user is created."""

    user_id: uuid.UUID
    email: str
    event_name: str = "identity.user_created"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class IdentityUserAuthenticatedEvent(Event):
    """Event published after an identity user authenticates."""

    user_id: uuid.UUID
    email: str
    event_name: str = "identity.user_authenticated"
    occurred_at: datetime = field(default_factory=utc_now)
