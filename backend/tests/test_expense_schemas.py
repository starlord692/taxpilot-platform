"""Tests for Expense Management Pydantic schemas."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

import app.modules.business.models  # noqa: F401
import app.modules.identity.models  # noqa: F401
from app.modules.expenses.models import (
    Expense,
    ExpenseCategory,
    ExpenseLine,
    ExpenseStatus,
    Vendor,
)
from app.modules.expenses.schemas import (
    ExpenseCreate,
    ExpenseLineCreate,
    ExpenseResponse,
    VendorCreate,
    VendorResponse,
)


def build_vendor_payload() -> dict[str, object]:
    """Build a valid vendor create payload."""
    return {
        "name": "Aarav Supplies",
        "email": "BILLING@EXAMPLE.COM",
        "phone": "+919876543210",
        "gstin": "29ABCDE1234F1Z5",
        "pan": "ABCDE1234F",
        "address": "Bengaluru",
        "is_active": True,
    }


def build_expense_payload() -> dict[str, object]:
    """Build a valid expense create payload."""
    return {
        "vendor_id": str(uuid.uuid4()),
        "expense_date": "2026-05-01",
        "category": "software",
        "description": "Accounting software subscription",
        "subtotal": "1000.00",
        "tax_amount": "180.00",
        "total_amount": "1180.00",
        "notes": "Annual subscription",
        "attachment_count": 1,
        "status": "draft",
        "lines": [
            {
                "description": "Cloud hosting",
                "quantity": "2.00",
                "unit_cost": "500.00",
                "tax_rate": "18.00",
                "line_total": "1180.00",
            }
        ],
    }


def test_vendor_schema_validation() -> None:
    """Vendor schema validates and normalizes supported values."""
    payload = build_vendor_payload()
    payload["name"] = "  Aarav   Supplies  "

    request = VendorCreate(**payload)

    assert request.name == "Aarav Supplies"
    assert request.email == "billing@example.com"
    assert request.gstin == "29ABCDE1234F1Z5"
    assert request.pan == "ABCDE1234F"


def test_invalid_vendor_email_is_rejected() -> None:
    """Vendor email must be valid when present."""
    payload = build_vendor_payload()
    payload["email"] = "not-an-email"

    with pytest.raises(ValidationError):
        VendorCreate(**payload)


def test_invalid_vendor_phone_is_rejected() -> None:
    """Vendor phone must use E.164 format."""
    payload = build_vendor_payload()
    payload["phone"] = "9876543210"

    with pytest.raises(ValidationError):
        VendorCreate(**payload)


def test_invalid_vendor_gstin_is_rejected() -> None:
    """Vendor GSTIN must match Indian GSTIN format when present."""
    payload = build_vendor_payload()
    payload["gstin"] = "invalid"

    with pytest.raises(ValidationError):
        VendorCreate(**payload)


def test_invalid_vendor_pan_is_rejected() -> None:
    """Vendor PAN must match Indian PAN format when present."""
    payload = build_vendor_payload()
    payload["pan"] = "invalid"

    with pytest.raises(ValidationError):
        VendorCreate(**payload)


def test_expense_schema_validation() -> None:
    """Expense schema validates valid payloads."""
    request = ExpenseCreate(**build_expense_payload())

    assert request.expense_date == date(2026, 5, 1)
    assert request.category == ExpenseCategory.SOFTWARE
    assert request.status == ExpenseStatus.DRAFT
    assert request.total_amount == Decimal("1180.00")
    assert len(request.lines) == 1


def test_expense_total_must_equal_subtotal_plus_tax() -> None:
    """Expense total must equal subtotal plus tax amount."""
    payload = build_expense_payload()
    payload["total_amount"] = "1179.00"

    with pytest.raises(ValidationError):
        ExpenseCreate(**payload)


def test_negative_expense_amount_is_rejected() -> None:
    """Expense amount fields must be non-negative."""
    payload = build_expense_payload()
    payload["subtotal"] = "-1.00"

    with pytest.raises(ValidationError):
        ExpenseCreate(**payload)


def test_negative_attachment_count_is_rejected() -> None:
    """Attachment count cannot be negative."""
    payload = build_expense_payload()
    payload["attachment_count"] = -1

    with pytest.raises(ValidationError):
        ExpenseCreate(**payload)


def test_invalid_expense_enum_is_rejected() -> None:
    """Expense category and status must be valid enums."""
    payload = build_expense_payload()
    payload["category"] = "invalid"

    with pytest.raises(ValidationError):
        ExpenseCreate(**payload)


def test_expense_line_validation() -> None:
    """Expense line schema validates valid payloads."""
    line = ExpenseLineCreate(
        description="Cloud hosting",
        quantity=Decimal("2.00"),
        unit_cost=Decimal("500.00"),
        tax_rate=Decimal("18.00"),
        line_total=Decimal("1180.00"),
    )

    assert line.quantity == Decimal("2.00")
    assert line.unit_cost == Decimal("500.00")


def test_expense_line_validation_failures() -> None:
    """Expense line rejects invalid quantity and amounts."""
    with pytest.raises(ValidationError):
        ExpenseLineCreate(
            description="Cloud hosting",
            quantity=Decimal("0.00"),
            unit_cost=Decimal("500.00"),
            line_total=Decimal("500.00"),
        )

    with pytest.raises(ValidationError):
        ExpenseLineCreate(
            description="Cloud hosting",
            quantity=Decimal("1.00"),
            unit_cost=Decimal("-1.00"),
            line_total=Decimal("500.00"),
        )


def test_vendor_response_serialization() -> None:
    """Vendor responses serialize from SQLAlchemy model attributes."""
    vendor_id = uuid.uuid4()
    business_id = uuid.uuid4()
    vendor = Vendor(
        id=vendor_id,
        business_id=business_id,
        vendor_code="VEND-0001",
        name="Aarav Supplies",
        email="billing@example.com",
        phone="+919876543210",
        gstin="29ABCDE1234F1Z5",
        pan="ABCDE1234F",
        address="Bengaluru",
        is_active=True,
    )

    response = VendorResponse.model_validate(vendor)

    assert response.id == vendor_id
    assert response.business_id == business_id
    assert response.vendor_code == "VEND-0001"
    assert response.email == "billing@example.com"


def test_expense_response_serialization() -> None:
    """Expense responses serialize nested vendor and lines."""
    expense_id = uuid.uuid4()
    vendor_id = uuid.uuid4()
    line_id = uuid.uuid4()
    business_id = uuid.uuid4()
    expense = Expense(
        id=expense_id,
        business_id=business_id,
        vendor_id=vendor_id,
        expense_number="EXP-0001",
        expense_date=date(2026, 5, 1),
        category=ExpenseCategory.SOFTWARE,
        description="Accounting software subscription",
        status=ExpenseStatus.APPROVED,
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        notes="Annual subscription",
        attachment_count=1,
        vendor=Vendor(
            id=vendor_id,
            business_id=business_id,
            vendor_code="VEND-0001",
            name="Aarav Supplies",
            is_active=True,
        ),
        lines=[
            ExpenseLine(
                id=line_id,
                expense_id=expense_id,
                description="Cloud hosting",
                quantity=Decimal("2.00"),
                unit_cost=Decimal("500.00"),
                tax_rate=Decimal("18.00"),
                line_total=Decimal("1180.00"),
            )
        ],
    )

    response = ExpenseResponse.model_validate(expense)

    assert response.id == expense_id
    assert response.vendor is not None
    assert response.vendor.id == vendor_id
    assert response.lines[0].id == line_id


def test_expense_responses_hide_internal_fields() -> None:
    """Expense responses do not expose audit, soft-delete, or version fields."""
    vendor = Vendor(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        vendor_code="VEND-0001",
        name="Aarav Supplies",
        is_active=True,
    )

    payload = VendorResponse.model_validate(vendor).model_dump()

    assert "created_at" not in payload
    assert "updated_at" not in payload
    assert "created_by" not in payload
    assert "updated_by" not in payload
    assert "is_deleted" not in payload
    assert "deleted_at" not in payload
    assert "version" not in payload
