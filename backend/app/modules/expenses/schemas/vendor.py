"""Vendor Pydantic schemas."""

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.expenses.validators import (
    validate_address,
    validate_email,
    validate_gstin,
    validate_pan,
    validate_phone,
    validate_vendor_name,
)


class ExpenseResponseBase(BaseModel):
    """Base expense response schema with ORM serialization support."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class VendorCreate(BaseModel):
    """Request schema for creating a vendor."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        description="Vendor display name.",
        examples=["Aarav Supplies"],
    )
    email: str | None = Field(
        default=None,
        description="Vendor email address.",
        examples=["billing@example.com"],
    )
    phone: str | None = Field(
        default=None,
        description="Vendor phone number in E.164 format.",
        examples=["+919876543210"],
    )
    gstin: str | None = Field(
        default=None,
        description="Indian Goods and Services Tax Identification Number.",
        examples=["29ABCDE1234F1Z5"],
    )
    pan: str | None = Field(
        default=None,
        description="Indian Permanent Account Number.",
        examples=["ABCDE1234F"],
    )
    address: str | None = Field(
        default=None,
        description="Vendor address.",
        examples=["42 Residency Road, Bengaluru"],
    )
    is_active: bool = Field(
        default=True,
        description="Whether the vendor is active.",
        examples=[True],
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Validate vendor name."""
        return validate_vendor_name(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        """Validate email when present."""
        return validate_email(value)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        """Validate phone when present."""
        return validate_phone(value)

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, value: str | None) -> str | None:
        """Validate GSTIN when present."""
        return validate_gstin(value)

    @field_validator("pan")
    @classmethod
    def validate_pan(cls, value: str | None) -> str | None:
        """Validate PAN when present."""
        return validate_pan(value)

    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str | None) -> str | None:
        """Validate address when present."""
        return validate_address(value)


class VendorUpdate(BaseModel):
    """Request schema for updating a vendor."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        default=None,
        description="Updated vendor display name.",
        examples=["Aarav Supplies"],
    )
    email: str | None = Field(
        default=None,
        description="Updated vendor email address.",
        examples=["billing@example.com"],
    )
    phone: str | None = Field(
        default=None,
        description="Updated vendor phone number in E.164 format.",
        examples=["+919876543210"],
    )
    gstin: str | None = Field(
        default=None,
        description="Updated vendor GSTIN.",
        examples=["29ABCDE1234F1Z5"],
    )
    pan: str | None = Field(
        default=None,
        description="Updated vendor PAN.",
        examples=["ABCDE1234F"],
    )
    address: str | None = Field(
        default=None,
        description="Updated vendor address.",
    )
    is_active: bool | None = Field(
        default=None,
        description="Whether the vendor is active.",
        examples=[True],
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        """Validate vendor name when present."""
        if value is None:
            return None
        return validate_vendor_name(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        """Validate email when present."""
        return validate_email(value)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        """Validate phone when present."""
        return validate_phone(value)

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, value: str | None) -> str | None:
        """Validate GSTIN when present."""
        return validate_gstin(value)

    @field_validator("pan")
    @classmethod
    def validate_pan(cls, value: str | None) -> str | None:
        """Validate PAN when present."""
        return validate_pan(value)

    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str | None) -> str | None:
        """Validate address when present."""
        return validate_address(value)


class VendorListResponse(ExpenseResponseBase):
    """Compact response schema for vendor lists."""

    id: uuid.UUID = Field(description="Vendor UUID.")
    business_id: uuid.UUID = Field(description="Business UUID.")
    vendor_code: str = Field(description="Business-scoped vendor code.")
    name: str = Field(description="Vendor display name.")
    email: str | None = Field(default=None, description="Vendor email address.")
    phone: str | None = Field(default=None, description="Vendor phone number.")
    is_active: bool = Field(description="Whether the vendor is active.")


class VendorResponse(VendorListResponse):
    """Response schema for a vendor."""

    gstin: str | None = Field(default=None, description="Vendor GSTIN.")
    pan: str | None = Field(default=None, description="Vendor PAN.")
    address: str | None = Field(default=None, description="Vendor address.")
