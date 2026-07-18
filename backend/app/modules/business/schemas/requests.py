"""Business request schemas."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.business.models import BusinessType, RegistrationStatus
from app.modules.business.validators import (
    validate_business_email,
    validate_business_name,
    validate_business_phone,
    validate_currency,
    validate_financial_year_start,
    validate_gstin,
    validate_language,
    validate_membership_role,
    validate_pan,
    validate_timezone,
    validate_trade_name,
    validate_website,
)


class BusinessAddressRequest(BaseModel):
    """Request schema for a business address."""

    model_config = ConfigDict(extra="forbid")

    address_line_1: str = Field(
        description="Primary business address line.",
        examples=["42 Residency Road"],
        min_length=1,
        max_length=255,
    )
    address_line_2: str | None = Field(
        default=None,
        description="Optional secondary business address line.",
        examples=["Suite 1201"],
        max_length=255,
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
        max_length=20,
    )


class BusinessTaxProfileRequest(BaseModel):
    """Request schema for a business tax profile."""

    model_config = ConfigDict(extra="forbid")

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
        max_length=10,
    )
    financial_year_start: date = Field(
        description="Financial year start date; month and day must form a valid date.",
        examples=["2026-04-01"],
    )
    gst_registered: bool = Field(
        default=False,
        description="Whether the business is GST registered.",
        examples=[True],
    )
    composition_scheme: bool = Field(
        default=False,
        description="Whether the business is under the GST composition scheme.",
        examples=[False],
    )

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, gstin: str | None) -> str | None:
        """Validate GSTIN when present."""
        return validate_gstin(gstin)

    @field_validator("pan")
    @classmethod
    def validate_pan(cls, pan: str | None) -> str | None:
        """Validate PAN when present."""
        return validate_pan(pan)

    @field_validator("financial_year_start")
    @classmethod
    def validate_financial_year_start(cls, value: date) -> date:
        """Validate financial year start."""
        return validate_financial_year_start(value)


class BusinessSettingsRequest(BaseModel):
    """Request schema for business settings."""

    model_config = ConfigDict(extra="forbid")

    currency: str = Field(
        default="INR",
        description="ISO-4217 currency code used by the business.",
        examples=["INR"],
    )
    timezone: str = Field(
        default="Asia/Kolkata",
        description="IANA timezone name used by the business.",
        examples=["Asia/Kolkata"],
    )
    date_format: str = Field(
        default="DD/MM/YYYY",
        description="Preferred business date display format.",
        examples=["DD/MM/YYYY"],
        max_length=30,
    )
    language: str = Field(
        default="en",
        description="ISO language code used for business localization.",
        examples=["en"],
    )

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, currency: str) -> str:
        """Validate currency code."""
        return validate_currency(currency)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, timezone: str) -> str:
        """Validate IANA timezone."""
        return validate_timezone(timezone)

    @field_validator("language")
    @classmethod
    def validate_language(cls, language: str) -> str:
        """Validate language code."""
        return validate_language(language)


class CreateBusinessRequest(BaseModel):
    """Request schema for creating a business."""

    model_config = ConfigDict(extra="forbid")

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
    registration_status: RegistrationStatus = Field(
        default=RegistrationStatus.PENDING,
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
        description="Business website URL using HTTP or HTTPS.",
        examples=["https://example.com"],
    )
    address: BusinessAddressRequest | None = Field(
        default=None,
        description="Optional business address.",
    )
    tax_profile: BusinessTaxProfileRequest | None = Field(
        default=None,
        description="Optional business tax profile.",
    )
    settings: BusinessSettingsRequest | None = Field(
        default=None,
        description="Optional business localization settings.",
    )

    @field_validator("legal_name")
    @classmethod
    def validate_legal_name(cls, legal_name: str) -> str:
        """Validate legal business name."""
        return validate_business_name(legal_name)

    @field_validator("trade_name")
    @classmethod
    def validate_trade_name(cls, trade_name: str | None) -> str | None:
        """Validate trade name when present."""
        return validate_trade_name(trade_name)

    @field_validator("business_email")
    @classmethod
    def validate_business_email(cls, email: str | None) -> str | None:
        """Validate business email when present."""
        return validate_business_email(email)

    @field_validator("business_phone")
    @classmethod
    def validate_business_phone(cls, phone: str | None) -> str | None:
        """Validate business phone when present."""
        return validate_business_phone(phone)

    @field_validator("website")
    @classmethod
    def validate_website(cls, website: str | None) -> str | None:
        """Validate business website when present."""
        return validate_website(website)


class UpdateBusinessRequest(BaseModel):
    """Request schema for updating a business."""

    model_config = ConfigDict(extra="forbid")

    legal_name: str | None = Field(
        default=None,
        description="Updated registered legal name of the business.",
        examples=["TaxPilot Labs Private Limited"],
    )
    trade_name: str | None = Field(
        default=None,
        description="Updated public or trade name of the business.",
        examples=["TaxPilot Labs"],
    )
    business_type: BusinessType | None = Field(
        default=None,
        description="Updated legal structure of the business.",
        examples=[BusinessType.PRIVATE_LIMITED],
    )
    registration_status: RegistrationStatus | None = Field(
        default=None,
        description="Updated government registration status.",
        examples=[RegistrationStatus.REGISTERED],
    )
    business_email: str | None = Field(
        default=None,
        description="Updated primary business email address.",
        examples=["accounts@example.com"],
    )
    business_phone: str | None = Field(
        default=None,
        description="Updated primary business phone number in E.164 format.",
        examples=["+919876543210"],
    )
    website: str | None = Field(
        default=None,
        description="Updated business website URL using HTTP or HTTPS.",
        examples=["https://example.com"],
    )
    address: BusinessAddressRequest | None = Field(
        default=None,
        description="Updated business address.",
    )
    tax_profile: BusinessTaxProfileRequest | None = Field(
        default=None,
        description="Updated business tax profile.",
    )
    settings: BusinessSettingsRequest | None = Field(
        default=None,
        description="Updated business localization settings.",
    )

    @field_validator("legal_name")
    @classmethod
    def validate_legal_name(cls, legal_name: str | None) -> str | None:
        """Validate legal business name when present."""
        if legal_name is None:
            return None
        return validate_business_name(legal_name)

    @field_validator("trade_name")
    @classmethod
    def validate_trade_name(cls, trade_name: str | None) -> str | None:
        """Validate trade name when present."""
        return validate_trade_name(trade_name)

    @field_validator("business_email")
    @classmethod
    def validate_business_email(cls, email: str | None) -> str | None:
        """Validate business email when present."""
        return validate_business_email(email)

    @field_validator("business_phone")
    @classmethod
    def validate_business_phone(cls, phone: str | None) -> str | None:
        """Validate business phone when present."""
        return validate_business_phone(phone)

    @field_validator("website")
    @classmethod
    def validate_website(cls, website: str | None) -> str | None:
        """Validate business website when present."""
        return validate_website(website)


class InviteMemberRequest(BaseModel):
    """Request schema for inviting a business member."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(
        description="Email address of the invited member.",
        examples=["member@example.com"],
    )
    role: str = Field(
        description="Business membership role to assign.",
        examples=["admin"],
        max_length=80,
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, email: str) -> str:
        """Validate invite email."""
        return validate_business_email(email) or email

    @field_validator("role")
    @classmethod
    def validate_role(cls, role: str) -> str:
        """Validate invite role."""
        return validate_membership_role(role)
