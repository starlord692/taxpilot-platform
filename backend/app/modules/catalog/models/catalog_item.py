"""Catalog persistence models."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Enum,
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
from app.modules.catalog.models.enums import CatalogItemStatus, ItemType


class CatalogItem(BaseEntity):
    __tablename__ = "catalog_items"
    __table_args__ = (
        UniqueConstraint("business_id", "code", name="uq_catalog_items_business_code"),
        Index("ix_catalog_items_business_type", "business_id", "item_type"),
        Index("ix_catalog_items_name", "name"),
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_type: Mapped[ItemType] = mapped_column(
        Enum(ItemType, native_enum=False, length=16), nullable=False
    )
    status: Mapped[CatalogItemStatus] = mapped_column(
        Enum(CatalogItemStatus, native_enum=False, length=16),
        default=CatalogItemStatus.ACTIVE,
        nullable=False,
    )
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    purchase_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0.00"), nullable=False
    )
    selling_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0.00"), nullable=False
    )
    default_unit: Mapped[str] = mapped_column(String(30), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hsn_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    sac_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    gst_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0.00"), nullable=False
    )
    cess_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0.00"), nullable=False
    )
    inventory_profile: Mapped[InventoryItemProfile | None] = relationship(
        back_populates="catalog_item", uselist=False, cascade="all, delete-orphan"
    )


class InventoryItemProfile(BaseEntity):
    __tablename__ = "inventory_item_profiles"
    __table_args__ = (
        UniqueConstraint("catalog_item_id", name="uq_inventory_profiles_catalog_item"),
    )
    catalog_item_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("catalog_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_product_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("inventory_products.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
    )
    stock_tracking: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reorder_level: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    opening_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    opening_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    default_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("inventory_warehouses.id", ondelete="SET NULL"),
        nullable=True,
    )
    catalog_item: Mapped[CatalogItem] = relationship(back_populates="inventory_profile")
