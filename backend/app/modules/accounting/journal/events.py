"""Journal lifecycle events."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.common.events import Event
from app.common.models.abstract.timestamp import utc_now


@dataclass(frozen=True)
class JournalPostedEvent(Event):
    """Event published after a journal entry is posted."""

    journal_id: uuid.UUID
    event_name: str = "journal.posted"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class JournalReversedEvent(Event):
    """Event published after a journal entry is reversed."""

    journal_id: uuid.UUID
    event_name: str = "journal.reversed"
    occurred_at: datetime = field(default_factory=utc_now)
