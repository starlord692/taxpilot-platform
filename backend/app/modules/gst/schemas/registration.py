"""GST registration schemas."""

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.gst.models import GSTRegistrationType
from app.modules.gst.schemas.validators import validate_gstin


class GSTRegistrationCreate(BaseModel):
    """Request schema for creating GST registration information."""

    model_config = ConfigDict(extra="forbid")

    gstin: str = Field(
        ...,
        description="Indian GSTIN.",
        examples=["29ABCDE1234F1Z5"],
    )
    legal_name: str = Field(
        ...,
        min_length=3,
        max_length=150,
        description="GST registered legal name.",
        examples=["Aarav Technologies Private Limited"],
    )
    trade_name: str | None = Field(
        default=None,
        max_length=150,
        description="Optional GST registered trade name.",
        examples=["Aarav Tech"],
    )
    registration_type: GSTRegistrationType = Field(
        ...,
        description="GST registration type.",
        examples=[GSTRegistrationType.REGULAR],
    )
    state_code: str = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Two-digit GST state code.",
        examples=["29"],
    )
    registration_date: date = Field(
        ...,
        description="GST registration date.",
        examples=["2026-04-01"],
    )
    is_composition_scheme: bool = Field(
        default=False,
        description="Whether the business uses the GST composition scheme.",
        examples=[False],
    )
    is_active: bool = Field(
        default=True,
        description="Whether this registration is active.",
        examples=[True],
    )

    @field_validator("gstin")
    @classmethod
    def validate_registration_gstin(cls, value: str) -> str:
        """Validate GSTIN."""
        return validate_gstin(value)

    @field_validator("state_code")
    @classmethod
    def validate_state_code(cls, value: str) -> str:
        """Validate GST state code."""
        normalized = value.strip()
        if not normalized.isdigit():
            raise ValueError("state_code must contain two digits")
        return normalized


class GSTRegistrationUpdate(BaseModel):
    """Request schema for updating GST registration information."""

    model_config = ConfigDict(extra="forbid")

    legal_name: str | None = Field(
        default=None,
        min_length=3,
        max_length=150,
        description="GST registered legal name.",
        examples=["Aarav Technologies Private Limited"],
    )
    trade_name: str | None = Field(
        default=None,
        max_length=150,
        description="Optional GST registered trade name.",
        examples=["Aarav Tech"],
    )
    registration_type: GSTRegistrationType | None = Field(
        default=None,
        description="GST registration type.",
        examples=[GSTRegistrationType.REGULAR],
    )
    registration_date: date | None = Field(
        default=None,
        description="GST registration date.",
        examples=["2026-04-01"],
    )
    is_composition_scheme: bool | None = Field(
        default=None,
        description="Whether the business uses the GST composition scheme.",
        examples=[False],
    )
    is_active: bool | None = Field(
        default=None,
        description="Whether this registration is active.",
        examples=[True],
    )


class GSTRegistrationResponse(BaseModel):
    """Response schema for GST registration information."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    gstin: str
    legal_name: str
    trade_name: str | None
    registration_type: GSTRegistrationType
    state_code: str
    registration_date: date
    is_composition_scheme: bool
    is_active: bool
