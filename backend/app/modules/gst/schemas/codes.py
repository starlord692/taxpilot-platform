"""GST HSN and SAC code schemas."""

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.gst.schemas.validators import validate_hsn_code, validate_sac_code


class HSNCodeCreate(BaseModel):
    """Request schema for creating an HSN code."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., description="HSN code.", examples=["847130"])
    description: str = Field(..., min_length=2, examples=["Portable computers"])
    default_tax_rate_id: uuid.UUID | None = Field(default=None)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        """Validate HSN code."""
        return validate_hsn_code(value)


class HSNCodeUpdate(BaseModel):
    """Request schema for updating an HSN code."""

    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(default=None, min_length=2)
    default_tax_rate_id: uuid.UUID | None = Field(default=None)


class HSNCodeResponse(BaseModel):
    """Response schema for an HSN code."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    description: str
    default_tax_rate_id: uuid.UUID | None


class SACCodeCreate(BaseModel):
    """Request schema for creating a SAC code."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., description="SAC code.", examples=["998314"])
    description: str = Field(..., min_length=2, examples=["IT consulting"])
    default_tax_rate_id: uuid.UUID | None = Field(default=None)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        """Validate SAC code."""
        return validate_sac_code(value)


class SACCodeUpdate(BaseModel):
    """Request schema for updating a SAC code."""

    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(default=None, min_length=2)
    default_tax_rate_id: uuid.UUID | None = Field(default=None)


class SACCodeResponse(BaseModel):
    """Response schema for a SAC code."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    description: str
    default_tax_rate_id: uuid.UUID | None
