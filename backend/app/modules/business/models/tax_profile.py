"""Business tax profile model."""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity

if TYPE_CHECKING:
    from app.modules.business.models.business import Business


class BusinessTaxProfile(BaseEntity):
    """Tax profile for a business."""

    __tablename__ = "business_tax_profiles"
    __table_args__ = (
        Index("ix_business_tax_profiles_business_id", "business_id"),
        Index("ix_business_tax_profiles_gstin", "gstin"),
        Index("ix_business_tax_profiles_pan", "pan"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    pan: Mapped[str | None] = mapped_column(String(10), nullable=True)
    tan: Mapped[str | None] = mapped_column(String(10), nullable=True)
    financial_year_start: Mapped[date] = mapped_column(Date, nullable=False)
    gst_registered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    composition_scheme: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    business: Mapped[Business] = relationship(back_populates="tax_profile")
