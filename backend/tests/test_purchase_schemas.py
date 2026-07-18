"""Tests for Purchase Management Pydantic schemas."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

import app.modules.business.models  # noqa: F401
import app.modules.identity.models  # noqa: F401
from app.modules.purchases.models import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    PurchaseStatus,
    Supplier,
)
from app.modules.purchases.schemas import (
    PurchaseInvoiceCreate,
    PurchaseInvoiceLineCreate,
    PurchaseInvoiceResponse,
    SupplierCreate,
    SupplierResponse,
)


def build_supplier_payload() -> dict[str, object]:
    """Build a valid supplier create payload."""
    return {
        "name": "Aarav Wholesale",
        "email": "BILLING@EXAMPLE.COM",
        "phone": "+919876543210",
        "gstin": "29ABCDE1234F1Z5",
        "pan": "ABCDE1234F",
        "address": "Bengaluru",
        "payment_terms": "Net 30",
        "is_active": True,
    }


def build_purchase_payload() -> dict[str, object]:
    """Build a valid purchase invoice create payload."""
    return {
        "supplier_id": str(uuid.uuid4()),
        "invoice_number": "SUP-INV-0001",
        "invoice_date": "2026-06-01",
        "due_date": "2026-06-30",
        "subtotal": "1000.00",
        "tax_amount": "180.00",
        "total_amount": "1180.00",
        "notes": "Office equipment",
        "attachment_count": 1,
        "status": "draft",
        "lines": [
            {
                "description": "Office laptops",
                "quantity": "2.00",
                "unit_cost": "500.00",
                "tax_rate": "18.00",
                "line_total": "1180.00",
            }
        ],
    }


def test_valid_supplier_creation() -> None:
    """Supplier schema validates and normalizes supported values."""
    payload = build_supplier_payload()
    payload["name"] = "  Aarav   Wholesale  "

    request = SupplierCreate(**payload)

    assert request.name == "Aarav Wholesale"
    assert request.email == "billing@example.com"
    assert request.gstin == "29ABCDE1234F1Z5"
    assert request.pan == "ABCDE1234F"
    assert request.payment_terms == "Net 30"


def test_invalid_supplier_gstin_is_rejected() -> None:
    """Supplier GSTIN must match Indian GSTIN format when present."""
    payload = build_supplier_payload()
    payload["gstin"] = "invalid"

    with pytest.raises(ValidationError):
        SupplierCreate(**payload)


def test_invalid_supplier_pan_is_rejected() -> None:
    """Supplier PAN must match Indian PAN format when present."""
    payload = build_supplier_payload()
    payload["pan"] = "invalid"

    with pytest.raises(ValidationError):
        SupplierCreate(**payload)


def test_invalid_supplier_email_is_rejected() -> None:
    """Supplier email must be valid when present."""
    payload = build_supplier_payload()
    payload["email"] = "not-an-email"

    with pytest.raises(ValidationError):
        SupplierCreate(**payload)


def test_invalid_supplier_phone_is_rejected() -> None:
    """Supplier phone must use E.164 format."""
    payload = build_supplier_payload()
    payload["phone"] = "9876543210"

    with pytest.raises(ValidationError):
        SupplierCreate(**payload)


def test_negative_purchase_subtotal_is_rejected() -> None:
    """Purchase subtotal cannot be negative."""
    payload = build_purchase_payload()
    payload["subtotal"] = "-1.00"

    with pytest.raises(ValidationError):
        PurchaseInvoiceCreate(**payload)


def test_negative_purchase_tax_is_rejected() -> None:
    """Purchase tax cannot be negative."""
    payload = build_purchase_payload()
    payload["tax_amount"] = "-1.00"

    with pytest.raises(ValidationError):
        PurchaseInvoiceCreate(**payload)


def test_negative_purchase_line_quantity_is_rejected() -> None:
    """Purchase line quantity must be positive."""
    with pytest.raises(ValidationError):
        PurchaseInvoiceLineCreate(
            description="Office laptops",
            quantity=Decimal("-1.00"),
            unit_cost=Decimal("500.00"),
            line_total=Decimal("500.00"),
        )


def test_invalid_due_date_is_rejected() -> None:
    """Purchase due date cannot be before invoice date."""
    payload = build_purchase_payload()
    payload["due_date"] = "2026-05-31"

    with pytest.raises(ValidationError):
        PurchaseInvoiceCreate(**payload)


def test_incorrect_total_amount_is_rejected() -> None:
    """Purchase total must equal subtotal plus tax amount."""
    payload = build_purchase_payload()
    payload["total_amount"] = "1179.00"

    with pytest.raises(ValidationError):
        PurchaseInvoiceCreate(**payload)


def test_invalid_purchase_enum_is_rejected() -> None:
    """Purchase status must be a valid enum."""
    payload = build_purchase_payload()
    payload["status"] = "invalid"

    with pytest.raises(ValidationError):
        PurchaseInvoiceCreate(**payload)


def test_purchase_schema_validation() -> None:
    """Purchase invoice schema validates valid payloads."""
    request = PurchaseInvoiceCreate(**build_purchase_payload())

    assert request.supplier_id is not None
    assert request.invoice_date == date(2026, 6, 1)
    assert request.status == PurchaseStatus.DRAFT
    assert request.total_amount == Decimal("1180.00")
    assert len(request.lines) == 1


def test_supplier_response_serialization() -> None:
    """Supplier responses serialize from SQLAlchemy model attributes."""
    supplier_id = uuid.uuid4()
    business_id = uuid.uuid4()
    supplier = Supplier(
        id=supplier_id,
        business_id=business_id,
        supplier_code="SUP-0001",
        name="Aarav Wholesale",
        email="billing@example.com",
        phone="+919876543210",
        gstin="29ABCDE1234F1Z5",
        pan="ABCDE1234F",
        address="Bengaluru",
        payment_terms="Net 30",
        is_active=True,
    )

    response = SupplierResponse.model_validate(supplier)

    assert response.id == supplier_id
    assert response.business_id == business_id
    assert response.supplier_code == "SUP-0001"
    assert response.email == "billing@example.com"


def test_purchase_response_serialization() -> None:
    """Purchase responses serialize nested supplier and lines."""
    purchase_id = uuid.uuid4()
    supplier_id = uuid.uuid4()
    line_id = uuid.uuid4()
    business_id = uuid.uuid4()
    purchase_invoice = PurchaseInvoice(
        id=purchase_id,
        business_id=business_id,
        supplier_id=supplier_id,
        purchase_number="PUR-0001",
        invoice_number="SUP-INV-0001",
        invoice_date=date(2026, 6, 1),
        due_date=date(2026, 6, 30),
        status=PurchaseStatus.APPROVED,
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        notes="Office equipment",
        attachment_count=1,
        supplier=Supplier(
            id=supplier_id,
            business_id=business_id,
            supplier_code="SUP-0001",
            name="Aarav Wholesale",
            is_active=True,
        ),
        lines=[
            PurchaseInvoiceLine(
                id=line_id,
                purchase_invoice_id=purchase_id,
                description="Office laptops",
                quantity=Decimal("2.00"),
                unit_cost=Decimal("500.00"),
                tax_rate=Decimal("18.00"),
                line_total=Decimal("1180.00"),
            )
        ],
    )

    response = PurchaseInvoiceResponse.model_validate(purchase_invoice)

    assert response.id == purchase_id
    assert response.supplier is not None
    assert response.supplier.id == supplier_id
    assert response.lines[0].id == line_id


def test_purchase_responses_hide_internal_fields() -> None:
    """Purchase responses do not expose audit, soft-delete, or version fields."""
    supplier = Supplier(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        supplier_code="SUP-0001",
        name="Aarav Wholesale",
        is_active=True,
    )

    payload = SupplierResponse.model_validate(supplier).model_dump()

    assert "created_at" not in payload
    assert "updated_at" not in payload
    assert "created_by" not in payload
    assert "updated_by" not in payload
    assert "is_deleted" not in payload
    assert "deleted_at" not in payload
    assert "version" not in payload
