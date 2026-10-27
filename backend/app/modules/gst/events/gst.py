"""GST module events."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Self

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


@dataclass(frozen=True)
class GSTReconciliationCompletedEvent(Event):
    """Event published when a GST return reconciliation evaluation completes."""

    business_id: uuid.UUID
    tax_period: str
    status: str
    is_comparison_performed: bool = False
    is_matched: bool = False
    comparison_source: str = "unprovided"
    is_portal_verified: bool = False
    event_name: str = "gst.reconciliation.completed"
    occurred_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        """Validate trust-boundary and lifecycle invariants."""
        if self.comparison_source not in (
            "unprovided",
            "user_supplied",
            "government_portal",
        ):
            raise ValueError(
                f"GSTReconciliationCompletedEvent: unsupported comparison_source "
                f"'{self.comparison_source}'."
            )
        if self.is_portal_verified and self.comparison_source != "government_portal":
            raise ValueError(
                "GSTReconciliationCompletedEvent: is_portal_verified cannot be "
                f"True when comparison_source is '{self.comparison_source}'."
            )
        if self.comparison_source == "government_portal" or self.is_portal_verified:
            raise ValueError(
                "GSTReconciliationCompletedEvent: government portal provenance "
                "cannot be claimed without authorized server-side provider evidence."
            )
        if self.is_matched and (
            not self.is_comparison_performed or self.status != "matched"
        ):
            raise ValueError(
                "GSTReconciliationCompletedEvent: is_matched cannot be True "
                f"when is_comparison_performed is {self.is_comparison_performed} "
                f"and status is '{self.status}'."
            )
        if (self.status == "matched") != self.is_matched:
            raise ValueError(
                f"GSTReconciliationCompletedEvent: status '{self.status}' contradicts "
                f"is_matched={self.is_matched}."
            )

    @classmethod
    def from_report(cls, report: Any) -> Self:
        """Derive event directly from validated report for provenance integrity."""
        status_val = (
            report.status.value
            if hasattr(report.status, "value")
            else str(report.status)
        )
        source_val = (
            report.comparison_source.value
            if hasattr(report.comparison_source, "value")
            else str(report.comparison_source)
        )
        is_matched = (
            status_val == "matched"
            and getattr(report, "is_comparison_performed", False)
            and getattr(report, "is_outward_matched", False)
            and getattr(report, "is_itc_matched", False)
        )
        return cls(
            business_id=report.period.business_id,
            tax_period=report.period.tax_period,
            status=status_val,
            is_comparison_performed=report.is_comparison_performed,
            is_matched=is_matched,
            comparison_source=source_val,
            is_portal_verified=report.is_portal_verified,
        )


