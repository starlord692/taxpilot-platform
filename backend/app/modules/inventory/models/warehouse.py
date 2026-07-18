"""Warehouse model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity

if TYPE_CHECKING:
    from app.modules.business.models import Business
    from app.modules.inventory.models.stock_balance import StockBalance
    from app.modules.inventory.models.stock_movement import StockMovement


class Warehouse(BaseEntity):
    """Physical or logical warehouse owned by one business."""

    __tablename__ = "inventory_warehouses"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "code",
            name="uq_inventory_warehouses_business_code",
        ),
        Index("ix_inventory_warehouses_business_id", "business_id"),
        Index("ix_inventory_warehouses_code", "code"),
        Index("ix_inventory_warehouses_name", "name"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    business: Mapped[Business] = relationship()
    stock_balances: Mapped[list[StockBalance]] = relationship(
        back_populates="warehouse",
        cascade="all, delete-orphan",
    )
    stock_movements: Mapped[list[StockMovement]] = relationship(
        back_populates="warehouse",
    )
