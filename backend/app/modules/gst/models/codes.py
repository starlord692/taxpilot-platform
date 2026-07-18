"""HSN and SAC code models."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.modules.gst.models.tax_rate import GSTTaxRate


class HSNCode(BaseEntity):
    """HSN code tax classification."""

    __tablename__ = "gst_hsn_codes"
    __table_args__ = (
        Index("ix_gst_hsn_codes_code", "code", unique=True),
        Index("ix_gst_hsn_codes_default_tax_rate_id", "default_tax_rate_id"),
    )

    code: Mapped[str] = mapped_column(String(8), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    default_tax_rate_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("gst_tax_rates.id", ondelete="SET NULL"),
        nullable=True,
    )

    default_tax_rate: Mapped[GSTTaxRate | None] = relationship()


class SACCode(BaseEntity):
    """SAC code tax classification."""

    __tablename__ = "gst_sac_codes"
    __table_args__ = (
        Index("ix_gst_sac_codes_code", "code", unique=True),
        Index("ix_gst_sac_codes_default_tax_rate_id", "default_tax_rate_id"),
    )

    code: Mapped[str] = mapped_column(String(6), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    default_tax_rate_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("gst_tax_rates.id", ondelete="SET NULL"),
        nullable=True,
    )

    default_tax_rate: Mapped[GSTTaxRate | None] = relationship()
