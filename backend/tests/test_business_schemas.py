"""Tests for business Pydantic schemas."""

import uuid
from datetime import date

import pytest
from pydantic import ValidationError

from app.modules.business.models import (
    Business,
    BusinessAddress,
    BusinessSettings,
    BusinessStatus,
    BusinessTaxProfile,
    BusinessType,
    RegistrationStatus,
)
from app.modules.business.schemas import (
    BusinessResponse,
    BusinessSettingsRequest,
    BusinessTaxProfileRequest,
    CreateBusinessRequest,
)


def build_business_payload() -> dict[str, object]:
    """Build a valid business create payload."""
    return {
        "legal_name": "TaxPilot Labs Private Limited",
        "trade_name": "TaxPilot Labs",
        "business_type": "private_limited",
        "registration_status": "registered",
        "business_email": "ACCOUNTS@EXAMPLE.COM",
        "business_phone": "+919876543210",
        "website": "https://example.com",
        "address": {
            "address_line_1": "42 Residency Road",
            "address_line_2": "Suite 1201",
            "city": "Bengaluru",
            "state": "Karnataka",
            "country": "India",
            "postal_code": "560025",
        },
        "tax_profile": {
            "gstin": "29ABCDE1234F1Z5",
            "pan": "ABCDE1234F",
            "tan": "BLRA12345B",
            "financial_year_start": "2026-04-01",
            "gst_registered": True,
            "composition_scheme": False,
        },
        "settings": {
            "currency": "INR",
            "timezone": "Asia/Kolkata",
            "date_format": "DD/MM/YYYY",
            "language": "en",
        },
    }


def test_invalid_email_is_rejected() -> None:
    """Business email must be valid."""
    payload = build_business_payload()
    payload["business_email"] = "not-an-email"

    with pytest.raises(ValidationError):
        CreateBusinessRequest(**payload)


def test_invalid_gstin_is_rejected() -> None:
    """GSTIN must match Indian GSTIN format when present."""
    with pytest.raises(ValidationError):
        BusinessTaxProfileRequest(
            gstin="invalid",
            pan="ABCDE1234F",
            financial_year_start=date(2026, 4, 1),
        )


def test_invalid_pan_is_rejected() -> None:
    """PAN must match Indian PAN format when present."""
    with pytest.raises(ValidationError):
        BusinessTaxProfileRequest(
            gstin="29ABCDE1234F1Z5",
            pan="invalid",
            financial_year_start=date(2026, 4, 1),
        )


def test_invalid_url_is_rejected() -> None:
    """Business website must be a valid HTTP or HTTPS URL."""
    payload = build_business_payload()
    payload["website"] = "ftp://example.com"

    with pytest.raises(ValidationError):
        CreateBusinessRequest(**payload)


def test_invalid_timezone_is_rejected() -> None:
    """Timezone must be a valid IANA timezone."""
    with pytest.raises(ValidationError):
        BusinessSettingsRequest(timezone="Mars/Olympus")


def test_invalid_currency_is_rejected() -> None:
    """Currency must be an uppercase ISO-4217 code shape."""
    with pytest.raises(ValidationError):
        BusinessSettingsRequest(currency="Rupees")


def test_invalid_language_is_rejected() -> None:
    """Language must be an ISO-style language code."""
    with pytest.raises(ValidationError):
        BusinessSettingsRequest(language="english")


def test_invalid_phone_number_is_rejected() -> None:
    """Phone number must be E.164-compatible."""
    payload = build_business_payload()
    payload["business_phone"] = "9876543210"

    with pytest.raises(ValidationError):
        CreateBusinessRequest(**payload)


def test_business_name_length_is_validated() -> None:
    """Business legal name must be between 3 and 150 characters."""
    payload = build_business_payload()
    payload["legal_name"] = "AB"

    with pytest.raises(ValidationError):
        CreateBusinessRequest(**payload)


def test_create_business_request_normalizes_values() -> None:
    """Business request validators normalize supported input values."""
    payload = build_business_payload()
    payload["legal_name"] = "  TaxPilot   Labs Private Limited  "

    request = CreateBusinessRequest(**payload)

    assert request.legal_name == "TaxPilot Labs Private Limited"
    assert request.business_email == "accounts@example.com"
    assert request.tax_profile is not None
    assert request.tax_profile.gstin == "29ABCDE1234F1Z5"
    assert request.tax_profile.pan == "ABCDE1234F"


def test_business_response_orm_serialization() -> None:
    """Business responses serialize from SQLAlchemy model attributes."""
    business_id = uuid.uuid4()
    address_id = uuid.uuid4()
    tax_profile_id = uuid.uuid4()
    settings_id = uuid.uuid4()
    business = Business(
        id=business_id,
        legal_name="TaxPilot Labs Private Limited",
        trade_name="TaxPilot Labs",
        business_type=BusinessType.PRIVATE_LIMITED,
        registration_status=RegistrationStatus.REGISTERED,
        business_email="accounts@example.com",
        business_phone="+919876543210",
        website="https://example.com",
        logo_url="https://example.com/logo.png",
        status=BusinessStatus.ACTIVE,
        address=BusinessAddress(
            id=address_id,
            business_id=business_id,
            address_line_1="42 Residency Road",
            address_line_2=None,
            city="Bengaluru",
            state="Karnataka",
            country="India",
            postal_code="560025",
        ),
        tax_profile=BusinessTaxProfile(
            id=tax_profile_id,
            business_id=business_id,
            gstin="29ABCDE1234F1Z5",
            pan="ABCDE1234F",
            tan="BLRA12345B",
            financial_year_start=date(2026, 4, 1),
            gst_registered=True,
            composition_scheme=False,
        ),
        settings=BusinessSettings(
            id=settings_id,
            business_id=business_id,
            currency="INR",
            timezone="Asia/Kolkata",
            date_format="DD/MM/YYYY",
            language="en",
        ),
    )

    response = BusinessResponse.model_validate(business)

    assert response.id == business_id
    assert response.address is not None
    assert response.address.id == address_id
    assert response.tax_profile is not None
    assert response.tax_profile.id == tax_profile_id
    assert response.settings is not None
    assert response.settings.id == settings_id


def test_business_response_hides_internal_fields() -> None:
    """Business responses do not expose audit, soft-delete, or version fields."""
    business = Business(
        id=uuid.uuid4(),
        legal_name="TaxPilot Labs Private Limited",
        business_type=BusinessType.PRIVATE_LIMITED,
        registration_status=RegistrationStatus.REGISTERED,
        status=BusinessStatus.ACTIVE,
    )

    payload = BusinessResponse.model_validate(business).model_dump()

    assert "created_at" not in payload
    assert "updated_at" not in payload
    assert "created_by" not in payload
    assert "updated_by" not in payload
    assert "is_deleted" not in payload
    assert "deleted_at" not in payload
    assert "version" not in payload
