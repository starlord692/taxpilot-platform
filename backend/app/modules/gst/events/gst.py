"""GST module events."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.common.events import Event
from app.common.models.abstract.timestamp import utc_now


@dataclass(frozen=True)
class GSTRegistrationCreatedEvent(Event):
    """Event published when GST registration is created."""

    registration_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "gst.registration.created"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class GSTRegistrationUpdatedEvent(Event):
    """Event published when GST registration is updated."""

    registration_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "gst.registration.updated"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class GSTTaxRateChangedEvent(Event):
    """Event published when a GST tax rate changes."""

    tax_rate_id: uuid.UUID
    event_name: str = "gst.tax_rate.changed"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class GSTSettingsChangedEvent(Event):
    """Event published when GST settings change."""

    settings_id: uuid.UUID
    business_id: uuid.UUID
    event_name: str = "gst.settings.changed"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class GSTCalculatedEvent(Event):
    """Event published when GST is calculated."""

    business_id: uuid.UUID
    source_type: str
    source_id: uuid.UUID | None = None
    event_name: str = "gst.calculated"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class GSTRecalculatedEvent(Event):
    """Event published when GST is recalculated."""

    business_id: uuid.UUID
    source_type: str
    source_id: uuid.UUID | None = None
    event_name: str = "gst.recalculated"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class GSTReturnGeneratedEvent(Event):
    """Event published when a GST statutory report is generated."""

    business_id: uuid.UUID
    tax_period: str
    report_type: str
    event_name: str = "gst.return.generated"
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class GSTAuditCompletedEvent(Event):
    """Event published when a GST audit report is completed."""

    business_id: uuid.UUID
    tax_period: str
    issue_count: int
    event_name: str = "gst.audit.completed"
    occurred_at: datetime = field(default_factory=utc_now)
