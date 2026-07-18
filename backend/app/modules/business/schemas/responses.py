"""Business response schemas."""

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.modules.business.models import (
    BusinessStatus,
    BusinessType,
    RegistrationStatus,
)


class BusinessResponseBase(BaseModel):
    """Base business response schema with ORM serialization support."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class BusinessAddressResponse(BusinessResponseBase):
    """Response schema for a business address."""

    id: uuid.UUID = Field(
        description="Business address UUID.",
        examples=["018f1d3c-4f87-7b6f-8f25-6cfcdd17f8b4"],
    )
    business_id: uuid.UUID = Field(
        description="Business UUID that owns the address.",
        examples=["018f1d3c-4f87-7b6f-8f25-6cfcdd17f8b4"],
    )
    address_line_1: str = Field(
        description="Primary business address line.",
        examples=["42 Residency Road"],
    )
    address_line_2: str | None = Field(
        default=None,
        description="Optional secondary business address line.",
        examples=["Suite 1201"],
    )
    city: str = Field(description="Business city.", examples=["Bengaluru"])
    state: str = Field(
        description="Business state or province.",
        examples=["Karnataka"],
    )
    country: str = Field(description="Business country.", examples=["India"])
    postal_code: str = Field(
        description="Postal or ZIP code for the business address.",
        examples=["560025"],
    )


class BusinessTaxProfileResponse(BusinessResponseBase):
    """Response schema for a business tax profile."""

    id: uuid.UUID = Field(
        description="Business tax profile UUID.",
        examples=["018f1d3c-4f87-7b6f-8f25-6cfcdd17f8b4"],
    )
    business_id: uuid.UUID = Field(
        description="Business UUID that owns the tax profile.",
        examples=["018f1d3c-4f87-7b6f-8f25-6cfcdd17f8b4"],
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
    tan: str | None = Field(
        default=None,
        description="Indian Tax Deduction and Collection Account Number.",
        examples=["BLRA12345B"],
    )
    financial_year_start: date = Field(
        description="Financial year start date.",
        examples=["2026-04-01"],
    )
    gst_registered: bool = Field(
        description="Whether the business is GST registered.",
        examples=[True],
    )
    composition_scheme: bool = Field(
        description="Whether the business is under the GST composition scheme.",
        examples=[False],
    )


class BusinessSettingsResponse(BusinessResponseBase):
    """Response schema for business settings."""

    id: uuid.UUID = Field(
        description="Business settings UUID.",
        examples=["018f1d3c-4f87-7b6f-8f25-6cfcdd17f8b4"],
    )
    business_id: uuid.UUID = Field(
        description="Business UUID that owns the settings.",
        examples=["018f1d3c-4f87-7b6f-8f25-6cfcdd17f8b4"],
    )
    currency: str = Field(
        description="ISO-4217 currency code used by the business.",
        examples=["INR"],
    )
    timezone: str = Field(
        description="IANA timezone name used by the business.",
        examples=["Asia/Kolkata"],
    )
    date_format: str = Field(
        description="Preferred business date display format.",
        examples=["DD/MM/YYYY"],
    )
    language: str = Field(
        description="ISO language code used for business localization.",
        examples=["en"],
    )


class BusinessMembershipResponse(BusinessResponseBase):
    """Response schema for business membership."""

    id: uuid.UUID = Field(
        description="Business membership UUID.",
        examples=["018f1d3c-4f87-7b6f-8f25-6cfcdd17f8b4"],
    )
    business_id: uuid.UUID = Field(
        description="Business UUID for this membership.",
        examples=["018f1d3c-4f87-7b6f-8f25-6cfcdd17f8b4"],
    )
    user_id: uuid.UUID = Field(
        description="Identity user UUID for this membership.",
        examples=["018f1d3c-4f87-7b6f-8f25-6cfcdd17f8b4"],
    )
    role: str = Field(
        description="Business membership role.",
        examples=["admin"],
    )


class BusinessSummaryResponse(BusinessResponseBase):
    """Compact response schema for business lists and selectors."""

    id: uuid.UUID = Field(
        description="Business UUID.",
        examples=["018f1d3c-4f87-7b6f-8f25-6cfcdd17f8b4"],
    )
    legal_name: str = Field(
        description="Registered legal name of the business.",
        examples=["TaxPilot Labs Private Limited"],
    )
    trade_name: str | None = Field(
        default=None,
        description="Optional public or trade name of the business.",
        examples=["TaxPilot Labs"],
    )
    business_type: BusinessType = Field(
        description="Legal structure of the business.",
        examples=[BusinessType.PRIVATE_LIMITED],
    )
    status: BusinessStatus = Field(
        description="Current business lifecycle status.",
        examples=[BusinessStatus.ACTIVE],
    )


class BusinessResponse(BusinessSummaryResponse):
    """Full response schema for a business."""

    registration_status: RegistrationStatus = Field(
        description="Government registration status of the business.",
        examples=[RegistrationStatus.REGISTERED],
    )
    business_email: str | None = Field(
        default=None,
        description="Primary business email address.",
        examples=["accounts@example.com"],
    )
    business_phone: str | None = Field(
        default=None,
        description="Primary business phone number in E.164 format.",
        examples=["+919876543210"],
    )
    website: str | None = Field(
        default=None,
        description="Business website URL.",
        examples=["https://example.com"],
    )
    logo_url: str | None = Field(
        default=None,
        description="Business logo URL.",
        examples=["https://example.com/logo.png"],
    )
    address: BusinessAddressResponse | None = Field(
        default=None,
        description="Business address.",
    )
    tax_profile: BusinessTaxProfileResponse | None = Field(
        default=None,
        description="Business tax profile.",
    )
    settings: BusinessSettingsResponse | None = Field(
        default=None,
        description="Business localization settings.",
    )
