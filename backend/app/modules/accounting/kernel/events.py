"""Accounting kernel integration events."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.common.events import Event
from app.common.models.abstract.timestamp import utc_now


@dataclass(frozen=True)
class AccountingInvoicePostedEvent(Event):
    """Event published after a sales invoice is posted to accounting."""

    invoice_id: uuid.UUID
    journal_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "accounting.invoice_posted"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class AccountingPaymentPostedEvent(Event):
    """Event published after a customer payment is posted to accounting."""

    payment_id: uuid.UUID
    invoice_id: uuid.UUID
    journal_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "accounting.payment_posted"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class AccountingExpensePostedEvent(Event):
    """Event published after an approved expense is posted to accounting."""

    expense_id: uuid.UUID
    journal_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "accounting.expense_posted"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class AccountingExpensePaymentPostedEvent(Event):
    """Event published after an expense payment is posted to accounting."""

    expense_id: uuid.UUID
    journal_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "accounting.expense_payment_posted"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class AccountingPurchasePostedEvent(Event):
    """Event published after an approved purchase is posted to accounting."""

    purchase_id: uuid.UUID
    journal_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "accounting.purchase_posted"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class AccountingPurchasePaymentPostedEvent(Event):
    """Event published after a supplier payment is posted to accounting."""

    purchase_id: uuid.UUID
    journal_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "accounting.purchase_payment_posted"
    occurred_at: datetime = field(default_factory=utc_now)
