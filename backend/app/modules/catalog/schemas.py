"""Catalog API schemas and centralized business validation."""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.catalog.domain import TaxClassification
from app.modules.catalog.models import CatalogItemStatus, ItemType


class InventoryItemProfileResponse(BaseModel):
    """Inventory capability profile response schema."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    catalog_item_id: uuid.UUID
    legacy_product_id: uuid.UUID | None = None
    stock_tracking: bool = True
    reorder_level: Decimal | None = None
    default_warehouse_id: uuid.UUID | None = None


class CatalogItemCreate(BaseModel):
    """Request schema for creating a catalog item."""

    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    item_type: ItemType
    category: str | None = Field(default=None, max_length=120)
    purchase_price: Decimal = Field(default=Decimal("0.00"), ge=0)
    selling_price: Decimal = Field(default=Decimal("0.00"), ge=0)
    default_unit: str = Field(min_length=1, max_length=30)
    barcode: str | None = Field(default=None, max_length=100)
    hsn_code: str | None = Field(default=None, pattern=r"^\d{4,8}$")
    sac_code: str | None = Field(default=None, pattern=r"^\d{6,8}$")
    gst_rate: Decimal = Field(default=Decimal("0.00"), ge=0, le=100)
    cess_rate: Decimal = Field(default=Decimal("0.00"), ge=0, le=100)
    stock_tracking: bool | None = Field(default=None)
    default_warehouse_id: uuid.UUID | None = Field(default=None)
    legacy_product_id: uuid.UUID | None = Field(default=None)
    reorder_level: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_tax(self) -> "CatalogItemCreate":
        """Validate tax classification according to item type."""
        TaxClassification(
            self.hsn_code, self.sac_code, self.gst_rate, self.cess_rate
        ).validate_for(self.item_type)
        return self


class CatalogItemUpdate(BaseModel):
    """Request schema for updating a catalog item."""

    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    item_type: ItemType | None = None
    status: CatalogItemStatus | None = None
    category: str | None = Field(default=None, max_length=120)
    purchase_price: Decimal | None = Field(default=None, ge=0)
    selling_price: Decimal | None = Field(default=None, ge=0)
    default_unit: str | None = Field(default=None, min_length=1, max_length=30)
    barcode: str | None = Field(default=None, max_length=100)
    hsn_code: str | None = Field(default=None, pattern=r"^\d{4,8}$")
    sac_code: str | None = Field(default=None, pattern=r"^\d{6,8}$")
    gst_rate: Decimal | None = Field(default=None, ge=0, le=100)
    cess_rate: Decimal | None = Field(default=None, ge=0, le=100)
    default_warehouse_id: uuid.UUID | None = Field(default=None)
    reorder_level: Decimal | None = Field(default=None, ge=0)


class CatalogItemResponse(BaseModel):
    """Response schema for a single catalog item."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    business_id: uuid.UUID
    code: str | None
    name: str
    description: str | None
    item_type: ItemType
    status: CatalogItemStatus
    category: str | None
    purchase_price: Decimal
    selling_price: Decimal
    default_unit: str
    barcode: str | None
    hsn_code: str | None
    sac_code: str | None
    gst_rate: Decimal
    cess_rate: Decimal
    inventory_profile: InventoryItemProfileResponse | None = None


class CatalogItemListResponse(CatalogItemResponse):
    """Response schema for catalog item listings."""

    pass
