"""GST return period model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.common.models.abstract.timestamp import utc_now
from app.modules.gst.compliance.models.enums import (
    GSTFilingFrequency,
    GSTReturnStatus,
)

if TYPE_CHECKING:
    from app.modules.business.models import Business


class GSTReturnPeriod(BaseEntity):
    """GST return period generated for one business."""

    __tablename__ = "gst_return_periods"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "financial_year",
            "tax_period",
            name="uq_gst_return_period_business_period",
        ),
        Index("ix_gst_return_periods_business_id", "business_id"),
        Index("ix_gst_return_periods_tax_period", "tax_period"),
        Index("ix_gst_return_periods_status", "status"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    financial_year: Mapped[str] = mapped_column(String(9), nullable=False)
    tax_period: Mapped[str] = mapped_column(String(10), nullable=False)
    filing_frequency: Mapped[GSTFilingFrequency] = mapped_column(
        Enum(GSTFilingFrequency, name="gst_filing_frequency"),
        default=GSTFilingFrequency.MONTHLY,
        nullable=False,
    )
    status: Mapped[GSTReturnStatus] = mapped_column(
        Enum(GSTReturnStatus, name="gst_return_status"),
        default=GSTReturnStatus.GENERATED,
        nullable=False,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    filed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    business: Mapped[Business] = relationship()
