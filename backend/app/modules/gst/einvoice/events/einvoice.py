"""E-invoicing domain events."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.common.events import Event
from app.common.models.abstract.timestamp import utc_now


@dataclass(frozen=True)
class IRNGeneratedEvent(Event):
    """Event published when an IRN is generated."""

    business_id: uuid.UUID
    invoice_id: uuid.UUID
    irn: str
    event_name: str = "gst.einvoice.irn_generated"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class IRNCancelledEvent(Event):
    """Event published when an IRN is cancelled."""

    business_id: uuid.UUID
    invoice_id: uuid.UUID
    irn: str
    event_name: str = "gst.einvoice.irn_cancelled"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class EWayBillGeneratedEvent(Event):
    """Event published when an e-way bill is generated."""

    business_id: uuid.UUID
    invoice_id: uuid.UUID
    eway_bill_number: str
    event_name: str = "gst.ewaybill.generated"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class EWayBillCancelledEvent(Event):
    """Event published when an e-way bill is cancelled."""

    business_id: uuid.UUID
    invoice_id: uuid.UUID
    eway_bill_number: str
    event_name: str = "gst.ewaybill.cancelled"
    occurred_at: datetime = field(default_factory=utc_now)
