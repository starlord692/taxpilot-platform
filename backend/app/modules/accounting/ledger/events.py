"""Ledger lifecycle events."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.common.events import Event
from app.common.models.abstract.timestamp import utc_now


@dataclass(frozen=True)
class LedgerPostedEvent(Event):
    """Event published after a posted journal is written to ledger."""

    journal_id: uuid.UUID
    ledger_entry_count: int
    event_name: str = "ledger.posted"
    occurred_at: datetime = field(default_factory=utc_now)
