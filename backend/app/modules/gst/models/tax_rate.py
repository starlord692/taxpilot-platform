"""GST tax rate model."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models.abstract import BaseEntity


class GSTTaxRate(BaseEntity):
    """Reusable GST tax rate configuration."""

    __tablename__ = "gst_tax_rates"
    __table_args__ = (
        Index("ix_gst_tax_rates_name", "name"),
        Index("ix_gst_tax_rates_is_active", "is_active"),
        Index("ix_gst_tax_rates_effective_from", "effective_from"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    cgst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    sgst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    igst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    cess_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
