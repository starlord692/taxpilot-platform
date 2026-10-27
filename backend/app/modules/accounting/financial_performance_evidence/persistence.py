"""Accounting-owned AFPE persistence records.

These records store governed context and published evidence metadata. They do
not expose ORM objects through the AFPE consumer boundary.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    event,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models.abstract import BaseEntity


class AccountingObservationPeriodRecord(BaseEntity):
    """Stable Accounting-owned observation-period identity and state."""

    __tablename__ = "accounting_observation_periods"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "observation_period_id",
            name="uq_afpe_observation_period_business_identity",
        ),
        Index("ix_afpe_observation_period_business", "business_id"),
        CheckConstraint("period_start < period_end", name="ck_afpe_period_bounds"),
        CheckConstraint(
            "period_type IN ('CALENDAR', 'FISCAL')",
            name="ck_afpe_period_type",
        ),
        CheckConstraint(
            "inclusion_basis = 'POSTING_DATE'",
            name="ck_afpe_period_inclusion_basis",
        ),
        CheckConstraint(
            "period_state IN ('OPEN', 'CLOSED')",
            name="ck_afpe_period_state",
        ),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    observation_period_id: Mapped[str] = mapped_column(String(255), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    granularity: Mapped[str] = mapped_column(String(64), nullable=False)
    period_type: Mapped[str] = mapped_column(String(16), nullable=False)
    inclusion_basis: Mapped[str] = mapped_column(
        String(32), default="POSTING_DATE", nullable=False
    )
    period_policy_id: Mapped[str] = mapped_column(String(255), nullable=False)
    period_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    period_state: Mapped[str] = mapped_column(String(16), nullable=False)
    reconstruction_context_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    as_of: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AccountingComparisonContextRecord(BaseEntity):
    """Accounting-published permitted comparison context."""

    __tablename__ = "accounting_comparison_contexts"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "current_observation_period_id",
            "comparison_observation_period_id",
            "comparison_kind",
            name="uq_afpe_comparison_context",
        ),
        Index("ix_afpe_comparison_context_business", "business_id"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    current_observation_period_id: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    comparison_observation_period_id: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    comparison_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    availability_state: Mapped[str] = mapped_column(String(32), nullable=False)
    limitations: Mapped[list[dict[str, str]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    provenance: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    policy_context: Mapped[dict[str, str]] = mapped_column(
        JSON, default=dict, nullable=False
    )


class AccountingReconstructionContextRecord(BaseEntity):
    """Explicit point-in-time reconstruction context."""

    __tablename__ = "accounting_reconstruction_contexts"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "reconstruction_context_id",
            name="uq_afpe_reconstruction_context",
        ),
        Index("ix_afpe_reconstruction_business", "business_id"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reconstruction_context_id: Mapped[str] = mapped_column(String(255), nullable=False)
    observation_period_id: Mapped[str] = mapped_column(String(255), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    context_payload: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, nullable=False
    )


class AccountingHistoricalEvidenceRecord(BaseEntity):
    """Immutable published historical-reported evidence payload."""

    __tablename__ = "accounting_historical_evidence"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "evidence_result_id",
            name="uq_afpe_historical_evidence_identity",
        ),
        Index(
            "ix_afpe_historical_evidence_business_period",
            "business_id",
            "observation_period_id",
        ),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    observation_period_id: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_result_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    publication_event_id: Mapped[str] = mapped_column(String(255), nullable=False)


class AccountingEvidenceLineageRecord(BaseEntity):
    """Durable evidence lineage relationship."""

    __tablename__ = "accounting_evidence_lineage"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "evidence_result_id",
            "predecessor_evidence_result_id",
            "relationship_type",
            name="uq_afpe_evidence_lineage",
        ),
        Index("ix_afpe_lineage_business", "business_id"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    evidence_result_id: Mapped[str] = mapped_column(String(255), nullable=False)
    predecessor_evidence_result_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False)
    relationship_payload: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, nullable=False
    )


@event.listens_for(AccountingHistoricalEvidenceRecord, "before_update")
def _reject_historical_update(*_: object) -> None:
    """Published historical evidence is immutable."""

    raise ValueError("Published historical AFPE evidence is immutable")


@event.listens_for(AccountingHistoricalEvidenceRecord, "before_delete")
def _reject_historical_delete(*_: object) -> None:
    """Published historical evidence cannot be deleted."""

    raise ValueError("Published historical AFPE evidence cannot be deleted")


@event.listens_for(AccountingEvidenceLineageRecord, "before_update")
def _reject_lineage_update(*_: object) -> None:
    """Lineage relationships are immutable."""

    raise ValueError("AFPE evidence lineage is immutable")


@event.listens_for(AccountingEvidenceLineageRecord, "before_delete")
def _reject_lineage_delete(*_: object) -> None:
    """Lineage relationships cannot be deleted."""

    raise ValueError("AFPE evidence lineage cannot be deleted")


@event.listens_for(AccountingReconstructionContextRecord, "before_update")
def _reject_reconstruction_update(*_: object) -> None:
    """Reconstruction contexts are immutable reproducibility anchors."""

    raise ValueError("AFPE reconstruction context is immutable")


@event.listens_for(AccountingReconstructionContextRecord, "before_delete")
def _reject_reconstruction_delete(*_: object) -> None:
    """Reconstruction contexts cannot be deleted."""

    raise ValueError("AFPE reconstruction context cannot be deleted")
