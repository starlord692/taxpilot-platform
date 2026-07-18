"""GST settings model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.modules.gst.models.enums import GSTRoundingMethod, GSTTaxMode

if TYPE_CHECKING:
    from app.modules.business.models import Business


class GSTSettings(BaseEntity):
    """Business-specific GST behavior settings."""

    __tablename__ = "gst_settings"
    __table_args__ = (
        UniqueConstraint("business_id", name="uq_gst_settings_business_id"),
        Index("ix_gst_settings_business_id", "business_id"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    default_tax_mode: Mapped[GSTTaxMode] = mapped_column(
        Enum(GSTTaxMode, name="gst_tax_mode"),
        default=GSTTaxMode.INTRA_STATE,
        nullable=False,
    )
    tax_inclusive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rounding_method: Mapped[GSTRoundingMethod] = mapped_column(
        Enum(GSTRoundingMethod, name="gst_rounding_method"),
        default=GSTRoundingMethod.NEAREST,
        nullable=False,
    )
    allow_manual_override: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    business: Mapped[Business] = relationship()
