"""GST tax rate schemas."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.gst.schemas.validators import (
    validate_effective_dates,
    validate_tax_rate,
)


class GSTTaxRateCreate(BaseModel):
    """Request schema for creating a GST tax rate."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2, max_length=120, examples=["GST 18%"])
    cgst_rate: Decimal = Field(..., description="CGST rate percent.", examples=["9.00"])
    sgst_rate: Decimal = Field(..., description="SGST rate percent.", examples=["9.00"])
    igst_rate: Decimal = Field(
        ...,
        description="IGST rate percent.",
        examples=["18.00"],
    )
    cess_rate: Decimal = Field(
        default=Decimal("0.00"),
        description="Cess rate percent.",
        examples=["0.00"],
    )
    effective_from: date = Field(..., examples=["2026-04-01"])
    effective_to: date | None = Field(default=None, examples=["2027-03-31"])
    is_active: bool = Field(default=True, examples=[True])

    @field_validator("cgst_rate", "sgst_rate", "igst_rate", "cess_rate")
    @classmethod
    def validate_rates(cls, value: Decimal) -> Decimal:
        """Validate GST rates."""
        return validate_tax_rate(value)

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        """Validate effective dates."""
        validate_effective_dates(self.effective_from, self.effective_to)
        return self


class GSTTaxRateUpdate(BaseModel):
    """Request schema for updating a GST tax rate."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    cgst_rate: Decimal | None = Field(default=None)
    sgst_rate: Decimal | None = Field(default=None)
    igst_rate: Decimal | None = Field(default=None)
    cess_rate: Decimal | None = Field(default=None)
    effective_from: date | None = Field(default=None)
    effective_to: date | None = Field(default=None)
    is_active: bool | None = Field(default=None)

    @field_validator("cgst_rate", "sgst_rate", "igst_rate", "cess_rate")
    @classmethod
    def validate_rates(cls, value: Decimal | None) -> Decimal | None:
        """Validate GST rates."""
        return None if value is None else validate_tax_rate(value)


class GSTTaxRateResponse(BaseModel):
    """Response schema for a GST tax rate."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    cgst_rate: Decimal
    sgst_rate: Decimal
    igst_rate: Decimal
    cess_rate: Decimal
    effective_from: date
    effective_to: date | None
    is_active: bool
