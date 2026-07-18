"""Expense line Pydantic schemas."""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.expenses.schemas.vendor import ExpenseResponseBase
from app.modules.expenses.validators import (
    validate_non_negative_decimal,
    validate_positive_decimal,
    validate_required_text,
)


class ExpenseLineCreate(BaseModel):
    """Request schema for creating an expense line."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(
        description="Line item description.",
        examples=["Cloud hosting"],
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
    cgst_amount: Decimal = Field(default=Decimal("0.00"), examples=["90.00"])
    sgst_amount: Decimal = Field(default=Decimal("0.00"), examples=["90.00"])
    igst_amount: Decimal = Field(default=Decimal("0.00"), examples=["0.00"])
    cess_amount: Decimal = Field(default=Decimal("0.00"), examples=["0.00"])
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

    @field_validator(
        "unit_cost",
        "tax_rate",
        "cgst_amount",
        "sgst_amount",
        "igst_amount",
        "cess_amount",
        "line_total",
    )
    @classmethod
    def validate_non_negative_amounts(cls, value: Decimal) -> Decimal:
        """Validate non-negative decimal values."""
        return validate_non_negative_decimal(value, field_name="amount")


class ExpenseLineUpdate(BaseModel):
    """Request schema for updating an expense line."""

    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(
        default=None,
        description="Updated line item description.",
        examples=["Cloud hosting"],
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
    cgst_amount: Decimal | None = Field(default=None, examples=["90.00"])
    sgst_amount: Decimal | None = Field(default=None, examples=["90.00"])
    igst_amount: Decimal | None = Field(default=None, examples=["0.00"])
    cess_amount: Decimal | None = Field(default=None, examples=["0.00"])
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

    @field_validator(
        "unit_cost",
        "tax_rate",
        "cgst_amount",
        "sgst_amount",
        "igst_amount",
        "cess_amount",
        "line_total",
    )
    @classmethod
    def validate_non_negative_amounts(
        cls,
        value: Decimal | None,
    ) -> Decimal | None:
        """Validate optional non-negative decimal values."""
        if value is None:
            return None
        return validate_non_negative_decimal(value, field_name="amount")


class ExpenseLineResponse(ExpenseResponseBase):
    """Response schema for an expense line."""

    id: uuid.UUID = Field(description="Expense line UUID.")
    expense_id: uuid.UUID = Field(description="Expense UUID.")
    description: str = Field(description="Line item description.")
    quantity: Decimal = Field(description="Line quantity.")
    unit_cost: Decimal = Field(description="Line unit cost.")
    tax_rate: Decimal = Field(description="Line tax rate percentage.")
    cgst_amount: Decimal = Field(description="Line CGST amount.")
    sgst_amount: Decimal = Field(description="Line SGST amount.")
    igst_amount: Decimal = Field(description="Line IGST amount.")
    cess_amount: Decimal = Field(description="Line cess amount.")
    line_total: Decimal = Field(description="Line total amount.")

    @field_validator(
        "cgst_amount",
        "sgst_amount",
        "igst_amount",
        "cess_amount",
        mode="before",
    )
    @classmethod
    def default_missing_gst_component(cls, value: Decimal | None) -> Decimal:
        """Default legacy missing GST component values to zero."""
        return value or Decimal("0.00")
