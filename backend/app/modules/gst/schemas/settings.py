"""GST settings schemas."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.modules.gst.models import GSTRoundingMethod, GSTTaxMode


class GSTSettingsCreate(BaseModel):
    """Request schema for creating GST settings."""

    model_config = ConfigDict(extra="forbid")

    default_tax_mode: GSTTaxMode = Field(
        default=GSTTaxMode.INTRA_STATE,
        description="Default tax mode for this business.",
        examples=[GSTTaxMode.INTRA_STATE],
    )
    tax_inclusive: bool = Field(default=False, examples=[False])
    rounding_method: GSTRoundingMethod = Field(
        default=GSTRoundingMethod.NEAREST,
        examples=[GSTRoundingMethod.NEAREST],
    )
    allow_manual_override: bool = Field(default=False, examples=[False])


class GSTSettingsUpdate(BaseModel):
    """Request schema for updating GST settings."""

    model_config = ConfigDict(extra="forbid")

    default_tax_mode: GSTTaxMode | None = Field(default=None)
    tax_inclusive: bool | None = Field(default=None)
    rounding_method: GSTRoundingMethod | None = Field(default=None)
    allow_manual_override: bool | None = Field(default=None)


class GSTSettingsResponse(BaseModel):
    """Response schema for GST settings."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    default_tax_mode: GSTTaxMode
    tax_inclusive: bool
    rounding_method: GSTRoundingMethod
    allow_manual_override: bool
