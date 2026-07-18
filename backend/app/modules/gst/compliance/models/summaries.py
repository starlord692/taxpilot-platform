"""GST compliance summary snapshot models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models.abstract import BaseEntity
from app.common.models.abstract.timestamp import utc_now


class GSTR1Summary(BaseEntity):
    """GSTR-1 generated summary snapshot."""

    __tablename__ = "gst_gstr1_summaries"
    __table_args__ = (Index("ix_gst_gstr1_return_period_id", "return_period_id"),)

    return_period_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("gst_return_periods.id", ondelete="CASCADE"),
        nullable=False,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    taxable_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class GSTR3BSummary(BaseEntity):
    """GSTR-3B generated summary snapshot."""

    __tablename__ = "gst_gstr3b_summaries"
    __table_args__ = (Index("ix_gst_gstr3b_return_period_id", "return_period_id"),)

    return_period_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("gst_return_periods.id", ondelete="CASCADE"),
        nullable=False,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    outward_taxable_supplies: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )
    input_tax_credit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    net_gst_payable: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class ITCReconciliation(BaseEntity):
    """Input tax credit reconciliation snapshot."""

    __tablename__ = "gst_itc_reconciliations"
    __table_args__ = (Index("ix_gst_itc_return_period_id", "return_period_id"),)

    return_period_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("gst_return_periods.id", ondelete="CASCADE"),
        nullable=False,
    )
    eligible_itc: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    blocked_itc: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    rcm_itc: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    pending_itc: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class GSTAuditReport(BaseEntity):
    """GST audit report snapshot."""

    __tablename__ = "gst_audit_reports"
    __table_args__ = (Index("ix_gst_audit_reports_business_id", "business_id"),)

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        nullable=False,
    )
    tax_period: Mapped[str] = mapped_column(String(10), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    issue_count: Mapped[int] = mapped_column(nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
