"""Stock movement Pydantic schemas."""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.inventory.models import MovementType
from app.modules.inventory.schemas.product import InventoryResponseBase
from app.modules.inventory.validators import (
    validate_optional_text,
    validate_positive_decimal,
)


class StockMovementCreate(BaseModel):
    """Request schema for creating a stock movement."""

    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID = Field(
        description="Product UUID.",
        examples=[str(uuid.uuid4())],
    )
    warehouse_id: uuid.UUID = Field(
        description="Warehouse UUID.",
        examples=[str(uuid.uuid4())],
    )
    movement_type: MovementType = Field(
        description="Stock movement type.",
        examples=[MovementType.PURCHASE],
    )
    quantity: Decimal = Field(
        description="Movement quantity.",
        examples=["10.0000"],
    )
    reference_type: str | None = Field(
        default=None,
        description="External source entity type.",
        examples=["purchase_invoice"],
    )
    reference_id: uuid.UUID | None = Field(
        default=None,
        description="External source entity UUID.",
        examples=[str(uuid.uuid4())],
    )
    notes: str | None = Field(
        default=None,
        description="Optional stock movement notes.",
        examples=["Initial purchase receipt"],
    )

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, value: Decimal) -> Decimal:
        """Validate positive stock movement quantity."""
        return validate_positive_decimal(value, field_name="quantity")

    @field_validator("reference_type")
    @classmethod
    def validate_reference_type(cls, value: str | None) -> str | None:
        """Validate reference type when present."""
        return validate_optional_text(
            value,
            field_name="reference_type",
            max_length=80,
        )

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        """Validate notes when present."""
        return validate_optional_text(value, field_name="notes", max_length=2000)


class StockMovementResponse(InventoryResponseBase):
    """Response schema for a stock movement."""

    id: uuid.UUID = Field(description="Stock movement UUID.")
    business_id: uuid.UUID = Field(description="Business UUID.")
    product_id: uuid.UUID = Field(description="Product UUID.")
    warehouse_id: uuid.UUID = Field(description="Warehouse UUID.")
    movement_type: MovementType = Field(description="Stock movement type.")
    quantity: Decimal = Field(description="Movement quantity.")
    reference_type: str | None = Field(
        default=None,
        description="External source entity type.",
    )
    reference_id: uuid.UUID | None = Field(
        default=None,
        description="External source entity UUID.",
    )
    notes: str | None = Field(default=None, description="Stock movement notes.")


class StockMovementListResponse(StockMovementResponse):
    """Compact response schema for stock movement lists."""
