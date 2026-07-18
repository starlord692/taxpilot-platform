"""Product Pydantic schemas."""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.inventory.validators import (
    validate_non_negative_decimal,
    validate_optional_text,
    validate_required_text,
)


class InventoryResponseBase(BaseModel):
    """Base inventory response schema with ORM serialization support."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ProductCreate(BaseModel):
    """Request schema for creating an inventory product."""

    model_config = ConfigDict(extra="forbid")

    sku: str = Field(
        description="Business-scoped product SKU.",
        examples=["LAPTOP-001"],
        min_length=1,
        max_length=80,
    )
    name: str = Field(
        description="Product display name.",
        examples=["Business Laptop"],
        min_length=1,
        max_length=255,
    )
    description: str | None = Field(
        default=None,
        description="Product description.",
        examples=["14 inch laptop"],
    )
    category: str | None = Field(
        default=None,
        description="Product category.",
        examples=["Hardware"],
    )
    unit_of_measure: str = Field(
        description="Product unit of measure.",
        examples=["pcs"],
        min_length=1,
        max_length=30,
    )
    barcode: str | None = Field(
        default=None,
        description="Product barcode.",
        examples=["8900000000012"],
    )
    purchase_price: Decimal = Field(
        default=Decimal("0.00"),
        description="Default product purchase price.",
        examples=["50000.00"],
    )
    selling_price: Decimal = Field(
        default=Decimal("0.00"),
        description="Default product selling price.",
        examples=["65000.00"],
    )
    reorder_level: Decimal = Field(
        default=Decimal("0.0000"),
        description="Minimum desired stock quantity before reorder.",
        examples=["5.0000"],
    )
    is_active: bool = Field(
        default=True,
        description="Whether the product is active.",
        examples=[True],
    )

    @field_validator("sku")
    @classmethod
    def validate_sku(cls, value: str) -> str:
        """Validate product SKU."""
        return validate_required_text(value, field_name="sku", max_length=80)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Validate product name."""
        return validate_required_text(value, field_name="name", max_length=255)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        """Validate product description when present."""
        return validate_optional_text(
            value,
            field_name="description",
            max_length=2000,
        )

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str | None) -> str | None:
        """Validate product category when present."""
        return validate_optional_text(value, field_name="category", max_length=120)

    @field_validator("unit_of_measure")
    @classmethod
    def validate_unit_of_measure(cls, value: str) -> str:
        """Validate product unit of measure."""
        return validate_required_text(
            value,
            field_name="unit_of_measure",
            max_length=30,
        )

    @field_validator("barcode")
    @classmethod
    def validate_barcode(cls, value: str | None) -> str | None:
        """Validate product barcode when present."""
        return validate_optional_text(value, field_name="barcode", max_length=100)

    @field_validator("purchase_price", "selling_price")
    @classmethod
    def validate_prices(cls, value: Decimal) -> Decimal:
        """Validate non-negative product prices."""
        return validate_non_negative_decimal(value, field_name="price")

    @field_validator("reorder_level")
    @classmethod
    def validate_reorder_level(cls, value: Decimal) -> Decimal:
        """Validate non-negative reorder level."""
        return validate_non_negative_decimal(
            value,
            field_name="reorder_level",
            places=Decimal("0.0001"),
            max_exponent=-4,
        )


class ProductUpdate(BaseModel):
    """Request schema for updating an inventory product."""

    model_config = ConfigDict(extra="forbid")

    sku: str | None = Field(
        default=None,
        description="Updated business-scoped product SKU.",
        examples=["LAPTOP-002"],
        max_length=80,
    )
    name: str | None = Field(
        default=None,
        description="Updated product display name.",
        examples=["Business Laptop"],
        max_length=255,
    )
    description: str | None = Field(
        default=None,
        description="Updated product description.",
    )
    category: str | None = Field(
        default=None,
        description="Updated product category.",
        examples=["Hardware"],
    )
    unit_of_measure: str | None = Field(
        default=None,
        description="Updated product unit of measure.",
        examples=["pcs"],
        max_length=30,
    )
    barcode: str | None = Field(
        default=None,
        description="Updated product barcode.",
        examples=["8900000000012"],
    )
    purchase_price: Decimal | None = Field(
        default=None,
        description="Updated purchase price.",
        examples=["50000.00"],
    )
    selling_price: Decimal | None = Field(
        default=None,
        description="Updated selling price.",
        examples=["65000.00"],
    )
    reorder_level: Decimal | None = Field(
        default=None,
        description="Updated reorder level.",
        examples=["5.0000"],
    )
    is_active: bool | None = Field(
        default=None,
        description="Whether the product is active.",
        examples=[True],
    )

    @field_validator("sku")
    @classmethod
    def validate_sku(cls, value: str | None) -> str | None:
        """Validate SKU when present."""
        if value is None:
            return None
        return validate_required_text(value, field_name="sku", max_length=80)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        """Validate product name when present."""
        if value is None:
            return None
        return validate_required_text(value, field_name="name", max_length=255)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        """Validate product description when present."""
        return validate_optional_text(
            value,
            field_name="description",
            max_length=2000,
        )

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str | None) -> str | None:
        """Validate product category when present."""
        return validate_optional_text(value, field_name="category", max_length=120)

    @field_validator("unit_of_measure")
    @classmethod
    def validate_unit_of_measure(cls, value: str | None) -> str | None:
        """Validate unit of measure when present."""
        if value is None:
            return None
        return validate_required_text(
            value,
            field_name="unit_of_measure",
            max_length=30,
        )

    @field_validator("barcode")
    @classmethod
    def validate_barcode(cls, value: str | None) -> str | None:
        """Validate product barcode when present."""
        return validate_optional_text(value, field_name="barcode", max_length=100)

    @field_validator("purchase_price", "selling_price")
    @classmethod
    def validate_prices(cls, value: Decimal | None) -> Decimal | None:
        """Validate optional non-negative product prices."""
        if value is None:
            return None
        return validate_non_negative_decimal(value, field_name="price")

    @field_validator("reorder_level")
    @classmethod
    def validate_reorder_level(cls, value: Decimal | None) -> Decimal | None:
        """Validate optional non-negative reorder level."""
        if value is None:
            return None
        return validate_non_negative_decimal(
            value,
            field_name="reorder_level",
            places=Decimal("0.0001"),
            max_exponent=-4,
        )


class ProductListResponse(InventoryResponseBase):
    """Compact response schema for product lists."""

    id: uuid.UUID = Field(description="Product UUID.")
    business_id: uuid.UUID = Field(description="Business UUID.")
    sku: str = Field(description="Business-scoped product SKU.")
    name: str = Field(description="Product display name.")
    category: str | None = Field(default=None, description="Product category.")
    unit_of_measure: str = Field(description="Product unit of measure.")
    selling_price: Decimal = Field(description="Default product selling price.")
    reorder_level: Decimal = Field(description="Product reorder level.")
    is_active: bool = Field(description="Whether the product is active.")


class ProductResponse(ProductListResponse):
    """Response schema for an inventory product."""

    description: str | None = Field(default=None, description="Product description.")
    barcode: str | None = Field(default=None, description="Product barcode.")
    purchase_price: Decimal = Field(description="Default product purchase price.")
