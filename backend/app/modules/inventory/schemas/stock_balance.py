"""Stock balance Pydantic schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field, field_validator

from app.modules.inventory.schemas.product import InventoryResponseBase
from app.modules.inventory.validators import validate_non_negative_decimal


class StockBalanceResponse(InventoryResponseBase):
    """Response schema for stock balance."""

    id: uuid.UUID = Field(description="Stock balance UUID.")
    business_id: uuid.UUID = Field(description="Business UUID.")
    product_id: uuid.UUID = Field(description="Product UUID.")
    warehouse_id: uuid.UUID = Field(description="Warehouse UUID.")
    quantity_on_hand: Decimal = Field(description="Quantity physically on hand.")
    quantity_reserved: Decimal = Field(description="Quantity reserved for orders.")
    quantity_available: Decimal = Field(description="Quantity available for sale.")
    last_updated: datetime = Field(description="Last balance update timestamp.")

    @field_validator(
        "quantity_on_hand",
        "quantity_reserved",
        "quantity_available",
    )
    @classmethod
    def validate_quantities(cls, value: Decimal) -> Decimal:
        """Validate non-negative stock balance quantities."""
        return validate_non_negative_decimal(
            value,
            field_name="quantity",
            places=Decimal("0.0001"),
            max_exponent=-4,
        )


class StockBalanceListResponse(StockBalanceResponse):
    """Compact response schema for stock balance lists."""
