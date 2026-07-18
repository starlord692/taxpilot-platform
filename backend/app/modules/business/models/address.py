"""Business address model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity

if TYPE_CHECKING:
    from app.modules.business.models.business import Business


class BusinessAddress(BaseEntity):
    """Postal address for a business."""

    __tablename__ = "business_addresses"
    __table_args__ = (Index("ix_business_addresses_business_id", "business_id"),)

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    address_line_1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)

    business: Mapped[Business] = relationship(back_populates="address")
