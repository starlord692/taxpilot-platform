"""Stock movement model."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.modules.inventory.models.enums import MovementType

if TYPE_CHECKING:
    from app.modules.business.models import Business
    from app.modules.inventory.models.product import Product
    from app.modules.inventory.models.warehouse import Warehouse


class StockMovement(BaseEntity):
    """Immutable stock movement record for a product and warehouse."""

    __tablename__ = "inventory_stock_movements"
    __table_args__ = (
        Index("ix_inventory_stock_movements_business_id", "business_id"),
        Index("ix_inventory_stock_movements_product_id", "product_id"),
        Index("ix_inventory_stock_movements_warehouse_id", "warehouse_id"),
        Index("ix_inventory_stock_movements_movement_type", "movement_type"),
        Index("ix_inventory_stock_movements_created_at", "created_at"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("inventory_products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("inventory_warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    movement_type: Mapped[MovementType] = mapped_column(
        Enum(MovementType, name="inventory_movement_type"),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    business: Mapped[Business] = relationship()
    product: Mapped[Product] = relationship(back_populates="stock_movements")
    warehouse: Mapped[Warehouse] = relationship(back_populates="stock_movements")
