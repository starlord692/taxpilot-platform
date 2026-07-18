"""Stock balance model."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.common.models.abstract.timestamp import utc_now

if TYPE_CHECKING:
    from app.modules.business.models import Business
    from app.modules.inventory.models.product import Product
    from app.modules.inventory.models.warehouse import Warehouse


class StockBalance(BaseEntity):
    """Current stock balance for one product in one warehouse."""

    __tablename__ = "inventory_stock_balances"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "warehouse_id",
            name="uq_inventory_stock_balances_product_warehouse",
        ),
        Index("ix_inventory_stock_balances_business_id", "business_id"),
        Index("ix_inventory_stock_balances_product_id", "product_id"),
        Index("ix_inventory_stock_balances_warehouse_id", "warehouse_id"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("inventory_products.id", ondelete="CASCADE"),
        nullable=False,
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("inventory_warehouses.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity_on_hand: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        default=Decimal("0.0000"),
        nullable=False,
    )
    quantity_reserved: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        default=Decimal("0.0000"),
        nullable=False,
    )
    quantity_available: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        default=Decimal("0.0000"),
        nullable=False,
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    business: Mapped[Business] = relationship()
    product: Mapped[Product] = relationship(back_populates="stock_balances")
    warehouse: Mapped[Warehouse] = relationship(back_populates="stock_balances")
