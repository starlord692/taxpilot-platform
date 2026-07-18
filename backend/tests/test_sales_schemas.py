"""Tests for Sales Pydantic schemas."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.sales.models import (
    Customer,
    InvoiceStatus,
    Payment,
    PaymentMethod,
    SalesInvoice,
    SalesInvoiceLine,
)
from app.modules.sales.schemas import (
    CustomerCreateRequest,
    CustomerResponse,
    InvoiceCreateRequest,
    InvoiceLineRequest,
    InvoiceResponse,
    PaymentCreateRequest,
)


def build_customer_payload() -> dict[str, object]:
    """Build a valid customer create payload."""
    return {
        "business_id": str(uuid.uuid4()),
        "customer_code": "CUST-0001",
        "name": "Aarav Enterprises",
        "email": "BILLING@EXAMPLE.COM",
        "phone": "+919876543210",
        "gstin": "29ABCDE1234F1Z5",
        "pan": "ABCDE1234F",
        "billing_address": "Bengaluru",
        "shipping_address": "Mysuru",
    }


def build_invoice_payload() -> dict[str, object]:
    """Build a valid invoice create payload."""
    return {
        "business_id": str(uuid.uuid4()),
        "customer_id": str(uuid.uuid4()),
        "invoice_number": "INV-0001",
        "invoice_date": "2026-04-01",
        "due_date": "2026-04-30",
        "status": "draft",
        "subtotal": "1000.00",
        "discount_amount": "50.00",
        "taxable_amount": "950.00",
        "tax_amount": "171.00",
        "total_amount": "1121.00",
        "notes": "First invoice",
        "lines": [
            {
                "description": "Monthly bookkeeping",
                "quantity": "2.00",
                "unit_price": "500.00",
                "discount": "50.00",
                "tax_rate": "18.00",
                "line_total": "1121.00",
            }
        ],
    }


def test_invalid_email_is_rejected() -> None:
    """Customer email must be valid."""
    payload = build_customer_payload()
    payload["email"] = "not-an-email"

    with pytest.raises(ValidationError):
        CustomerCreateRequest(**payload)


def test_invalid_gstin_is_rejected() -> None:
    """GSTIN must match Indian GSTIN format when present."""
    payload = build_customer_payload()
    payload["gstin"] = "invalid"

    with pytest.raises(ValidationError):
        CustomerCreateRequest(**payload)


def test_invalid_pan_is_rejected() -> None:
    """PAN must match Indian PAN format when present."""
    payload = build_customer_payload()
    payload["pan"] = "invalid"

    with pytest.raises(ValidationError):
        CustomerCreateRequest(**payload)


def test_negative_quantity_is_rejected() -> None:
    """Invoice line quantity must be positive."""
    with pytest.raises(ValidationError):
        InvoiceLineRequest(
            description="Monthly bookkeeping",
            quantity=Decimal("-1.00"),
            unit_price=Decimal("500.00"),
            line_total=Decimal("500.00"),
        )


def test_zero_quantity_is_rejected() -> None:
    """Invoice line quantity cannot be zero."""
    with pytest.raises(ValidationError):
        InvoiceLineRequest(
            description="Monthly bookkeeping",
            quantity=Decimal("0.00"),
            unit_price=Decimal("500.00"),
            line_total=Decimal("500.00"),
        )


def test_negative_payment_amount_is_rejected() -> None:
    """Payment amount must be positive."""
    with pytest.raises(ValidationError):
        PaymentCreateRequest(
            invoice_id=uuid.uuid4(),
            payment_date=date(2026, 4, 10),
            amount=Decimal("-1.00"),
            payment_method=PaymentMethod.UPI,
        )


def test_decimal_precision_is_validated() -> None:
    """Money fields allow at most two decimal places."""
    payload = build_invoice_payload()
    payload["subtotal"] = "1000.123"

    with pytest.raises(ValidationError):
        InvoiceCreateRequest(**payload)


def test_invoice_dates_are_validated() -> None:
    """Invoice due date cannot be before invoice date."""
    payload = build_invoice_payload()
    payload["due_date"] = "2026-03-31"

    with pytest.raises(ValidationError):
        InvoiceCreateRequest(**payload)


def test_customer_request_normalizes_values() -> None:
    """Customer request validators normalize supported values."""
    payload = build_customer_payload()
    payload["name"] = "  Aarav   Enterprises  "

    request = CustomerCreateRequest(**payload)

    assert request.name == "Aarav Enterprises"
    assert request.email == "billing@example.com"
    assert request.gstin == "29ABCDE1234F1Z5"
    assert request.pan == "ABCDE1234F"


def test_customer_response_serialization() -> None:
    """Customer responses serialize from SQLAlchemy model attributes."""
    customer_id = uuid.uuid4()
    business_id = uuid.uuid4()
    customer = Customer(
        id=customer_id,
        business_id=business_id,
        customer_code="CUST-0001",
        name="Aarav Enterprises",
        email="billing@example.com",
        phone="+919876543210",
        gstin="29ABCDE1234F1Z5",
        pan="ABCDE1234F",
        billing_address="Bengaluru",
        shipping_address="Mysuru",
        is_active=True,
    )

    response = CustomerResponse.model_validate(customer)

    assert response.id == customer_id
    assert response.business_id == business_id
    assert response.customer_code == "CUST-0001"
    assert response.email == "billing@example.com"


def test_invoice_response_serialization() -> None:
    """Invoice responses serialize nested lines and payments."""
    invoice_id = uuid.uuid4()
    line_id = uuid.uuid4()
    payment_id = uuid.uuid4()
    invoice = SalesInvoice(
        id=invoice_id,
        business_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        invoice_number="INV-0001",
        invoice_date=date(2026, 4, 1),
        due_date=date(2026, 4, 30),
        status=InvoiceStatus.ISSUED,
        subtotal=Decimal("1000.00"),
        discount_amount=Decimal("50.00"),
        taxable_amount=Decimal("950.00"),
        tax_amount=Decimal("171.00"),
        total_amount=Decimal("1121.00"),
        notes="First invoice",
        lines=[
            SalesInvoiceLine(
                id=line_id,
                invoice_id=invoice_id,
                description="Monthly bookkeeping",
                quantity=Decimal("2.00"),
                unit_price=Decimal("500.00"),
                discount=Decimal("50.00"),
                tax_rate=Decimal("18.00"),
                line_total=Decimal("1121.00"),
            )
        ],
        payments=[
            Payment(
                id=payment_id,
                invoice_id=invoice_id,
                payment_date=date(2026, 4, 10),
                amount=Decimal("500.00"),
                payment_method=PaymentMethod.UPI,
                reference_number="UPI-123",
            )
        ],
    )

    response = InvoiceResponse.model_validate(invoice)

    assert response.id == invoice_id
    assert response.lines[0].id == line_id
    assert response.payments[0].id == payment_id


def test_sales_responses_hide_internal_fields() -> None:
    """Sales responses do not expose audit, soft-delete, or version fields."""
    customer = Customer(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        customer_code="CUST-0001",
        name="Aarav Enterprises",
        is_active=True,
    )

    payload = CustomerResponse.model_validate(customer).model_dump()

    assert "created_at" not in payload
    assert "updated_at" not in payload
    assert "created_by" not in payload
    assert "updated_by" not in payload
    assert "is_deleted" not in payload
    assert "deleted_at" not in payload
    assert "version" not in payload
