"""Tests for Sales and Invoice database model mappings."""

import uuid
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import cast

from sqlalchemy import Table, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, RelationshipProperty, configure_mappers

from app.modules.sales.models import (
    Customer,
    InvoiceStatus,
    Payment,
    PaymentMethod,
    SalesInvoice,
    SalesInvoiceLine,
)


def unique_constraint_sets(model: type[DeclarativeBase]) -> set[tuple[str, ...]]:
    """Return multi-column unique constraint column names for a mapped model."""
    table = cast(Table, model.__table__)
    constraints: Iterable[UniqueConstraint] = (
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    )
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in constraints
    }


def test_customer_creation() -> None:
    """Customer can be constructed with expected fields and defaults."""
    business_id = uuid.uuid4()
    customer = Customer(
        business_id=business_id,
        customer_code="CUST-0001",
        name="Aarav Enterprises",
        email="accounts@aarav.example",
        phone="+919876543210",
        gstin="29ABCDE1234F1Z5",
        pan="ABCDE1234F",
        billing_address="Bengaluru, Karnataka",
        shipping_address="Mysuru, Karnataka",
    )

    assert customer.business_id == business_id
    assert customer.customer_code == "CUST-0001"
    assert customer.name == "Aarav Enterprises"
    assert Customer.__table__.c.is_active.default is not None
    assert Customer.__table__.c.is_active.default.arg is True


def test_invoice_creation() -> None:
    """Sales invoice can be constructed with expected fields and defaults."""
    invoice = SalesInvoice(
        business_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        invoice_number="INV-0001",
        invoice_date=date(2026, 4, 1),
        due_date=date(2026, 4, 30),
        subtotal=Decimal("1000.00"),
        discount_amount=Decimal("50.00"),
        taxable_amount=Decimal("950.00"),
        tax_amount=Decimal("171.00"),
        total_amount=Decimal("1121.00"),
        notes="First invoice",
    )

    assert invoice.invoice_number == "INV-0001"
    assert invoice.invoice_date == date(2026, 4, 1)
    assert invoice.total_amount == Decimal("1121.00")
    assert SalesInvoice.__table__.c.status.default is not None
    assert SalesInvoice.__table__.c.status.default.arg == InvoiceStatus.DRAFT


def test_invoice_lines() -> None:
    """Sales invoice lines hold item amounts."""
    invoice_id = uuid.uuid4()
    line = SalesInvoiceLine(
        invoice_id=invoice_id,
        description="Monthly bookkeeping",
        quantity=Decimal("2.00"),
        unit_price=Decimal("500.00"),
        discount=Decimal("50.00"),
        tax_rate=Decimal("18.00"),
        line_total=Decimal("1121.00"),
    )

    assert line.invoice_id == invoice_id
    assert line.quantity == Decimal("2.00")
    assert line.unit_price == Decimal("500.00")
    assert line.line_total == Decimal("1121.00")


def test_payments() -> None:
    """Payments hold payment details for an invoice."""
    invoice_id = uuid.uuid4()
    payment = Payment(
        invoice_id=invoice_id,
        payment_date=date(2026, 4, 10),
        amount=Decimal("500.00"),
        payment_method=PaymentMethod.UPI,
        reference_number="UPI-123",
        notes="Partial payment",
    )

    assert payment.invoice_id == invoice_id
    assert payment.payment_date == date(2026, 4, 10)
    assert payment.amount == Decimal("500.00")
    assert payment.payment_method == PaymentMethod.UPI


def test_sales_relationships() -> None:
    """Sales models expose expected ownership relationships."""
    configure_mappers()

    customer_invoices = Customer.__mapper__.relationships["invoices"]
    invoice_customer = SalesInvoice.__mapper__.relationships["customer"]
    invoice_lines = SalesInvoice.__mapper__.relationships["lines"]
    invoice_payments = SalesInvoice.__mapper__.relationships["payments"]
    line_invoice = SalesInvoiceLine.__mapper__.relationships["invoice"]
    payment_invoice = Payment.__mapper__.relationships["invoice"]

    assert isinstance(customer_invoices, RelationshipProperty)
    assert isinstance(invoice_customer, RelationshipProperty)
    assert isinstance(invoice_lines, RelationshipProperty)
    assert isinstance(invoice_payments, RelationshipProperty)
    assert isinstance(line_invoice, RelationshipProperty)
    assert isinstance(payment_invoice, RelationshipProperty)
    assert customer_invoices.uselist is True
    assert invoice_customer.uselist is False
    assert invoice_lines.uselist is True
    assert invoice_payments.uselist is True
    assert line_invoice.uselist is False
    assert payment_invoice.uselist is False


def test_invoice_number_unique_per_business() -> None:
    """Invoice numbers are unique per business."""
    assert ("business_id", "invoice_number") in unique_constraint_sets(SalesInvoice)


def test_customer_code_unique_per_business() -> None:
    """Customer codes are unique per business."""
    assert ("business_id", "customer_code") in unique_constraint_sets(Customer)


def test_sales_enum_values() -> None:
    """Sales enums expose expected lifecycle and payment values."""
    assert InvoiceStatus.DRAFT.value == "draft"
    assert InvoiceStatus.ISSUED.value == "issued"
    assert InvoiceStatus.PARTIALLY_PAID.value == "partially_paid"
    assert InvoiceStatus.PAID.value == "paid"
    assert InvoiceStatus.CANCELLED.value == "cancelled"
    assert PaymentMethod.CASH.value == "cash"
    assert PaymentMethod.BANK_TRANSFER.value == "bank_transfer"
    assert PaymentMethod.UPI.value == "upi"
    assert PaymentMethod.CARD.value == "card"
    assert PaymentMethod.CHEQUE.value == "cheque"
    assert PaymentMethod.OTHER.value == "other"
