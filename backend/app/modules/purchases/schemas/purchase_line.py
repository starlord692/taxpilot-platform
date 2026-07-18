"""Purchase invoice line Pydantic schemas."""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.purchases.schemas.supplier import PurchaseResponseBase
from app.modules.purchases.validators import (
    validate_non_negative_decimal,
    validate_positive_decimal,
    validate_required_text,
)


class PurchaseInvoiceLineCreate(BaseModel):
    """Request schema for creating a purchase invoice line."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(
        description="Line item description.",
        examples=["Office laptops"],
        min_length=1,
        max_length=255,
    )
    quantity: Decimal = Field(description="Line quantity.", examples=["2.00"])
    unit_cost: Decimal = Field(description="Line unit cost.", examples=["500.00"])
    tax_rate: Decimal = Field(
        default=Decimal("0.00"),
        description="Line tax rate percentage.",
        examples=["18.00"],
    )
    line_total: Decimal = Field(description="Line total amount.", examples=["1180.00"])

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        """Validate line description."""
        return validate_required_text(
            value,
            field_name="description",
            max_length=255,
        )

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, value: Decimal) -> Decimal:
        """Validate positive quantity."""
        return validate_positive_decimal(value, field_name="quantity")

    @field_validator("unit_cost", "tax_rate", "line_total")
    @classmethod
    def validate_non_negative_amounts(cls, value: Decimal) -> Decimal:
        """Validate non-negative decimal values."""
        return validate_non_negative_decimal(value, field_name="amount")


class PurchaseInvoiceLineUpdate(BaseModel):
    """Request schema for updating a purchase invoice line."""

    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(
        default=None,
        description="Updated line item description.",
        examples=["Office laptops"],
        max_length=255,
    )
    quantity: Decimal | None = Field(
        default=None,
        description="Updated line quantity.",
        examples=["2.00"],
    )
    unit_cost: Decimal | None = Field(
        default=None,
        description="Updated line unit cost.",
        examples=["500.00"],
    )
    tax_rate: Decimal | None = Field(
        default=None,
        description="Updated line tax rate percentage.",
        examples=["18.00"],
    )
    line_total: Decimal | None = Field(
        default=None,
        description="Updated line total amount.",
        examples=["1180.00"],
    )

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        """Validate line description when present."""
        if value is None:
            return None
        return validate_required_text(
            value,
            field_name="description",
            max_length=255,
        )

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, value: Decimal | None) -> Decimal | None:
        """Validate optional positive quantity."""
        if value is None:
            return None
        return validate_positive_decimal(value, field_name="quantity")

    @field_validator("unit_cost", "tax_rate", "line_total")
    @classmethod
    def validate_non_negative_amounts(
        cls,
        value: Decimal | None,
    ) -> Decimal | None:
        """Validate optional non-negative decimal values."""
        if value is None:
            return None
        return validate_non_negative_decimal(value, field_name="amount")


class PurchaseInvoiceLineResponse(PurchaseResponseBase):
    """Response schema for a purchase invoice line."""

    id: uuid.UUID = Field(description="Purchase invoice line UUID.")
    purchase_invoice_id: uuid.UUID = Field(description="Purchase invoice UUID.")
    description: str = Field(description="Line item description.")
    quantity: Decimal = Field(description="Line quantity.")
    unit_cost: Decimal = Field(description="Line unit cost.")
    tax_rate: Decimal = Field(description="Line tax rate percentage.")
    line_total: Decimal = Field(description="Line total amount.")
