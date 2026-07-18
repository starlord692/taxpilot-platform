"""Vendor model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity

if TYPE_CHECKING:
    from app.modules.business.models import Business
    from app.modules.expenses.models.expense import Expense


class Vendor(BaseEntity):
    """Vendor owned by one business."""

    __tablename__ = "vendors"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "vendor_code",
            name="uq_vendors_business_vendor_code",
        ),
        Index("ix_vendors_business_id", "business_id"),
        Index("ix_vendors_vendor_code", "vendor_code"),
        Index("ix_vendors_name", "name"),
        Index("ix_vendors_email", "email"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    vendor_code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    pan: Mapped[str | None] = mapped_column(String(10), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    business: Mapped[Business] = relationship()
    expenses: Mapped[list[Expense]] = relationship(
        back_populates="vendor",
    )
