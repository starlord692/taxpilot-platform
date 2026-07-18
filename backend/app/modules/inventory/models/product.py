"""Product model."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity

if TYPE_CHECKING:
    from app.modules.business.models import Business
    from app.modules.inventory.models.stock_balance import StockBalance
    from app.modules.inventory.models.stock_movement import StockMovement


class Product(BaseEntity):
    """Inventory product owned by one business."""

    __tablename__ = "inventory_products"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "sku",
            name="uq_inventory_products_business_sku",
        ),
        Index("ix_inventory_products_business_id", "business_id"),
        Index("ix_inventory_products_sku", "sku"),
        Index("ix_inventory_products_category", "category"),
        Index("ix_inventory_products_barcode", "barcode"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    sku: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    unit_of_measure: Mapped[str] = mapped_column(String(30), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True)
    purchase_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    selling_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    reorder_level: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        default=Decimal("0.0000"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    business: Mapped[Business] = relationship()
    stock_balances: Mapped[list[StockBalance]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )
    stock_movements: Mapped[list[StockMovement]] = relationship(
        back_populates="product",
    )
