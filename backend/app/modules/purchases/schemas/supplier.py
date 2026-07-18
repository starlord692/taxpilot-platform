"""Supplier Pydantic schemas."""

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.purchases.validators import (
    validate_address,
    validate_email,
    validate_gstin,
    validate_pan,
    validate_payment_terms,
    validate_phone,
    validate_supplier_name,
)


class PurchaseResponseBase(BaseModel):
    """Base purchase response schema with ORM serialization support."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class SupplierCreate(BaseModel):
    """Request schema for creating a supplier."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        description="Supplier display name.",
        examples=["Aarav Wholesale"],
    )
    email: str | None = Field(
        default=None,
        description="Supplier email address.",
        examples=["billing@example.com"],
    )
    phone: str | None = Field(
        default=None,
        description="Supplier phone number in E.164 format.",
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
        description="Supplier address.",
        examples=["42 Residency Road, Bengaluru"],
    )
    payment_terms: str | None = Field(
        default=None,
        description="Supplier payment terms.",
        examples=["Net 30"],
    )
    is_active: bool = Field(
        default=True,
        description="Whether the supplier is active.",
        examples=[True],
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Validate supplier name."""
        return validate_supplier_name(value)

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

    @field_validator("payment_terms")
    @classmethod
    def validate_payment_terms(cls, value: str | None) -> str | None:
        """Validate payment terms when present."""
        return validate_payment_terms(value)


class SupplierUpdate(BaseModel):
    """Request schema for updating a supplier."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        default=None,
        description="Updated supplier display name.",
        examples=["Aarav Wholesale"],
    )
    email: str | None = Field(
        default=None,
        description="Updated supplier email address.",
        examples=["billing@example.com"],
    )
    phone: str | None = Field(
        default=None,
        description="Updated supplier phone number in E.164 format.",
        examples=["+919876543210"],
    )
    gstin: str | None = Field(
        default=None,
        description="Updated supplier GSTIN.",
        examples=["29ABCDE1234F1Z5"],
    )
    pan: str | None = Field(
        default=None,
        description="Updated supplier PAN.",
        examples=["ABCDE1234F"],
    )
    address: str | None = Field(
        default=None,
        description="Updated supplier address.",
    )
    payment_terms: str | None = Field(
        default=None,
        description="Updated supplier payment terms.",
        examples=["Net 30"],
    )
    is_active: bool | None = Field(
        default=None,
        description="Whether the supplier is active.",
        examples=[True],
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        """Validate supplier name when present."""
        if value is None:
            return None
        return validate_supplier_name(value)

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

    @field_validator("payment_terms")
    @classmethod
    def validate_payment_terms(cls, value: str | None) -> str | None:
        """Validate payment terms when present."""
        return validate_payment_terms(value)


class SupplierListResponse(PurchaseResponseBase):
    """Compact response schema for supplier lists."""

    id: uuid.UUID = Field(description="Supplier UUID.")
    business_id: uuid.UUID = Field(description="Business UUID.")
    supplier_code: str = Field(description="Business-scoped supplier code.")
    name: str = Field(description="Supplier display name.")
    email: str | None = Field(default=None, description="Supplier email address.")
    phone: str | None = Field(default=None, description="Supplier phone number.")
    payment_terms: str | None = Field(
        default=None,
        description="Supplier payment terms.",
    )
    is_active: bool = Field(description="Whether the supplier is active.")


class SupplierResponse(SupplierListResponse):
    """Response schema for a supplier."""

    gstin: str | None = Field(default=None, description="Supplier GSTIN.")
    pan: str | None = Field(default=None, description="Supplier PAN.")
    address: str | None = Field(default=None, description="Supplier address.")
