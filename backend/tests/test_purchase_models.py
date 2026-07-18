"""Tests for Purchase Management database model mappings."""

import uuid
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import cast

from sqlalchemy import Table, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, RelationshipProperty, configure_mappers

import app.modules.business.models  # noqa: F401
import app.modules.identity.models  # noqa: F401
from app.modules.purchases.models import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    PurchaseStatus,
    Supplier,
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


def test_supplier_creation() -> None:
    """Supplier can be constructed with expected fields and defaults."""
    business_id = uuid.uuid4()
    supplier = Supplier(
        business_id=business_id,
        supplier_code="SUP-0001",
        name="Aarav Wholesale",
        email="billing@aarav-wholesale.example",
        phone="+919876543210",
        gstin="29ABCDE1234F1Z5",
        pan="ABCDE1234F",
        address="Bengaluru, Karnataka",
        payment_terms="Net 30",
    )

    assert supplier.business_id == business_id
    assert supplier.supplier_code == "SUP-0001"
    assert supplier.name == "Aarav Wholesale"
    assert supplier.payment_terms == "Net 30"
    assert Supplier.__table__.c.is_active.default is not None
    assert Supplier.__table__.c.is_active.default.arg is True


def test_purchase_invoice_creation() -> None:
    """Purchase invoice can be constructed with expected fields and defaults."""
    supplier_id = uuid.uuid4()
    purchase_invoice = PurchaseInvoice(
        business_id=uuid.uuid4(),
        supplier_id=supplier_id,
        purchase_number="PUR-0001",
        invoice_number="SUP-INV-0001",
        invoice_date=date(2026, 6, 1),
        due_date=date(2026, 6, 30),
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        notes="Inventory purchase",
    )

    assert purchase_invoice.supplier_id == supplier_id
    assert purchase_invoice.purchase_number == "PUR-0001"
    assert purchase_invoice.invoice_number == "SUP-INV-0001"
    assert purchase_invoice.invoice_date == date(2026, 6, 1)
    assert purchase_invoice.total_amount == Decimal("1180.00")
    assert PurchaseInvoice.__table__.c.status.default is not None
    assert PurchaseInvoice.__table__.c.status.default.arg == PurchaseStatus.DRAFT
    assert PurchaseInvoice.__table__.c.attachment_count.default is not None
    assert PurchaseInvoice.__table__.c.attachment_count.default.arg == 0


def test_purchase_invoice_lines() -> None:
    """Purchase invoice lines hold item amounts."""
    purchase_invoice_id = uuid.uuid4()
    line = PurchaseInvoiceLine(
        purchase_invoice_id=purchase_invoice_id,
        description="Office laptops",
        quantity=Decimal("2.00"),
        unit_cost=Decimal("500.00"),
        tax_rate=Decimal("18.00"),
        line_total=Decimal("1180.00"),
    )

    assert line.purchase_invoice_id == purchase_invoice_id
    assert line.quantity == Decimal("2.00")
    assert line.unit_cost == Decimal("500.00")
    assert line.tax_rate == Decimal("18.00")
    assert line.line_total == Decimal("1180.00")


def test_purchase_relationships() -> None:
    """Purchase models expose expected ownership relationships."""
    configure_mappers()

    supplier_invoices = Supplier.__mapper__.relationships["purchase_invoices"]
    invoice_supplier = PurchaseInvoice.__mapper__.relationships["supplier"]
    invoice_lines = PurchaseInvoice.__mapper__.relationships["lines"]
    line_invoice = PurchaseInvoiceLine.__mapper__.relationships["purchase_invoice"]

    assert isinstance(supplier_invoices, RelationshipProperty)
    assert isinstance(invoice_supplier, RelationshipProperty)
    assert isinstance(invoice_lines, RelationshipProperty)
    assert isinstance(line_invoice, RelationshipProperty)
    assert supplier_invoices.uselist is True
    assert invoice_supplier.uselist is False
    assert invoice_lines.uselist is True
    assert line_invoice.uselist is False


def test_supplier_code_unique_per_business() -> None:
    """Supplier codes are unique per business."""
    assert ("business_id", "supplier_code") in unique_constraint_sets(Supplier)


def test_purchase_number_unique_per_business() -> None:
    """Purchase numbers are unique per business."""
    assert (
        "business_id",
        "purchase_number",
    ) in unique_constraint_sets(PurchaseInvoice)


def test_purchase_enum_values() -> None:
    """Purchase enum exposes expected lifecycle values."""
    assert PurchaseStatus.DRAFT.value == "draft"
    assert PurchaseStatus.APPROVED.value == "approved"
    assert PurchaseStatus.RECEIVED.value == "received"
    assert PurchaseStatus.PAID.value == "paid"
    assert PurchaseStatus.CANCELLED.value == "cancelled"
