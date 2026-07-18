"""Warehouse Pydantic schemas."""

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.inventory.schemas.product import InventoryResponseBase
from app.modules.inventory.validators import (
    validate_optional_text,
    validate_required_text,
)


class WarehouseCreate(BaseModel):
    """Request schema for creating an inventory warehouse."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(
        description="Business-scoped warehouse code.",
        examples=["MAIN"],
        min_length=1,
        max_length=50,
    )
    name: str = Field(
        description="Warehouse display name.",
        examples=["Main Warehouse"],
        min_length=1,
        max_length=255,
    )
    address: str | None = Field(
        default=None,
        description="Warehouse address.",
        examples=["Bengaluru"],
    )
    is_default: bool = Field(
        default=False,
        description="Whether this is the default warehouse.",
        examples=[False],
    )
    is_active: bool = Field(
        default=True,
        description="Whether the warehouse is active.",
        examples=[True],
    )

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        """Validate warehouse code."""
        return validate_required_text(value, field_name="code", max_length=50)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Validate warehouse name."""
        return validate_required_text(value, field_name="name", max_length=255)

    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str | None) -> str | None:
        """Validate warehouse address when present."""
        return validate_optional_text(value, field_name="address", max_length=2000)


class WarehouseUpdate(BaseModel):
    """Request schema for updating an inventory warehouse."""

    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(
        default=None,
        description="Updated business-scoped warehouse code.",
        examples=["MAIN"],
        max_length=50,
    )
    name: str | None = Field(
        default=None,
        description="Updated warehouse display name.",
        examples=["Main Warehouse"],
        max_length=255,
    )
    address: str | None = Field(
        default=None,
        description="Updated warehouse address.",
    )
    is_default: bool | None = Field(
        default=None,
        description="Whether this is the default warehouse.",
        examples=[False],
    )
    is_active: bool | None = Field(
        default=None,
        description="Whether the warehouse is active.",
        examples=[True],
    )

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str | None) -> str | None:
        """Validate warehouse code when present."""
        if value is None:
            return None
        return validate_required_text(value, field_name="code", max_length=50)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        """Validate warehouse name when present."""
        if value is None:
            return None
        return validate_required_text(value, field_name="name", max_length=255)

    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str | None) -> str | None:
        """Validate warehouse address when present."""
        return validate_optional_text(value, field_name="address", max_length=2000)


class WarehouseListResponse(InventoryResponseBase):
    """Compact response schema for warehouse lists."""

    id: uuid.UUID = Field(description="Warehouse UUID.")
    business_id: uuid.UUID = Field(description="Business UUID.")
    code: str = Field(description="Business-scoped warehouse code.")
    name: str = Field(description="Warehouse display name.")
    is_default: bool = Field(description="Whether this is the default warehouse.")
    is_active: bool = Field(description="Whether the warehouse is active.")


class WarehouseResponse(WarehouseListResponse):
    """Response schema for an inventory warehouse."""

    address: str | None = Field(default=None, description="Warehouse address.")
