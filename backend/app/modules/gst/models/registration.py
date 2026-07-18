"""GST registration model."""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.modules.gst.models.enums import GSTRegistrationType

if TYPE_CHECKING:
    from app.modules.business.models import Business


class GSTRegistration(BaseEntity):
    """Business GST registration information."""

    __tablename__ = "gst_registrations"
    __table_args__ = (
        UniqueConstraint("gstin", name="uq_gst_registrations_gstin"),
        Index("ix_gst_registrations_business_id", "business_id"),
        Index("ix_gst_registrations_gstin", "gstin"),
        Index("ix_gst_registrations_is_active", "is_active"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    gstin: Mapped[str] = mapped_column(String(15), nullable=False)
    legal_name: Mapped[str] = mapped_column(String(150), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    registration_type: Mapped[GSTRegistrationType] = mapped_column(
        Enum(GSTRegistrationType, name="gst_registration_type"),
        nullable=False,
    )
    state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    registration_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_composition_scheme: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    business: Mapped[Business] = relationship()
