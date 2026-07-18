"""Account balance lifecycle events."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.common.events import Event
from app.common.models.abstract.timestamp import utc_now


@dataclass(frozen=True)
class AccountBalanceUpdatedEvent(Event):
    """Event published after account balances are updated from ledger."""

    journal_id: uuid.UUID
    business_id: uuid.UUID
    account_ids: list[uuid.UUID]
    event_name: str = "account.balance.updated"
    occurred_at: datetime = field(default_factory=utc_now)
