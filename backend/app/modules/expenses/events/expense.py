"""Expense lifecycle events."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.common.events import Event
from app.common.models.abstract.timestamp import utc_now


@dataclass(frozen=True)
class ExpenseCreatedEvent(Event):
    """Event published after an expense is created."""

    expense_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "expense.created"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class ExpenseUpdatedEvent(Event):
    """Event published after an expense is updated."""

    expense_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "expense.updated"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class ExpenseApprovedEvent(Event):
    """Event published after an expense is approved."""

    expense_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "expense.approved"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class ExpensePaidEvent(Event):
    """Event published after an expense is marked paid."""

    expense_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "expense.paid"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class ExpenseCancelledEvent(Event):
    """Event published after an expense is cancelled."""

    expense_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "expense.cancelled"
    occurred_at: datetime = field(default_factory=utc_now)
