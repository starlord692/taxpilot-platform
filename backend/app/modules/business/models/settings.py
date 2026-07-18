"""Business settings model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity

if TYPE_CHECKING:
    from app.modules.business.models.business import Business


class BusinessSettings(BaseEntity):
    """Localization and formatting settings for a business."""

    __tablename__ = "business_settings"
    __table_args__ = (Index("ix_business_settings_business_id", "business_id"),)

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(100),
        default="Asia/Kolkata",
        nullable=False,
    )
    date_format: Mapped[str] = mapped_column(
        String(30),
        default="DD/MM/YYYY",
        nullable=False,
    )
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)

    business: Mapped[Business] = relationship(back_populates="settings")
