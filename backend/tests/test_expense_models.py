"""Tests for Expense Management database model mappings."""

import uuid
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import cast

from sqlalchemy import Table, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, RelationshipProperty, configure_mappers

import app.modules.business.models  # noqa: F401
import app.modules.identity.models  # noqa: F401
from app.modules.expenses.models import (
    Expense,
    ExpenseCategory,
    ExpenseLine,
    ExpenseStatus,
    Vendor,
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


def test_vendor_creation() -> None:
    """Vendor can be constructed with expected fields and defaults."""
    business_id = uuid.uuid4()
    vendor = Vendor(
        business_id=business_id,
        vendor_code="VEND-0001",
        name="Aarav Supplies",
        email="billing@aarav-supplies.example",
        phone="+919876543210",
        gstin="29ABCDE1234F1Z5",
        pan="ABCDE1234F",
        address="Bengaluru, Karnataka",
    )

    assert vendor.business_id == business_id
    assert vendor.vendor_code == "VEND-0001"
    assert vendor.name == "Aarav Supplies"
    assert Vendor.__table__.c.is_active.default is not None
    assert Vendor.__table__.c.is_active.default.arg is True


def test_expense_creation() -> None:
    """Expense can be constructed with expected fields and defaults."""
    vendor_id = uuid.uuid4()
    expense = Expense(
        business_id=uuid.uuid4(),
        vendor_id=vendor_id,
        expense_number="EXP-0001",
        expense_date=date(2026, 5, 1),
        category=ExpenseCategory.SOFTWARE,
        description="Accounting software subscription",
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        notes="Annual subscription",
    )

    assert expense.vendor_id == vendor_id
    assert expense.expense_number == "EXP-0001"
    assert expense.expense_date == date(2026, 5, 1)
    assert expense.category == ExpenseCategory.SOFTWARE
    assert expense.total_amount == Decimal("1180.00")
    assert Expense.__table__.c.status.default is not None
    assert Expense.__table__.c.status.default.arg == ExpenseStatus.DRAFT
    assert Expense.__table__.c.attachment_count.default is not None
    assert Expense.__table__.c.attachment_count.default.arg == 0


def test_expense_without_vendor() -> None:
    """Expense vendor is optional."""
    expense = Expense(
        business_id=uuid.uuid4(),
        expense_number="EXP-0002",
        expense_date=date(2026, 5, 2),
        category=ExpenseCategory.OTHER,
    )

    assert expense.vendor_id is None


def test_expense_lines() -> None:
    """Expense lines hold item amounts."""
    expense_id = uuid.uuid4()
    line = ExpenseLine(
        expense_id=expense_id,
        description="Cloud hosting",
        quantity=Decimal("2.00"),
        unit_cost=Decimal("500.00"),
        tax_rate=Decimal("18.00"),
        line_total=Decimal("1180.00"),
    )

    assert line.expense_id == expense_id
    assert line.quantity == Decimal("2.00")
    assert line.unit_cost == Decimal("500.00")
    assert line.tax_rate == Decimal("18.00")
    assert line.line_total == Decimal("1180.00")


def test_expense_relationships() -> None:
    """Expense models expose expected ownership relationships."""
    configure_mappers()

    vendor_expenses = Vendor.__mapper__.relationships["expenses"]
    expense_vendor = Expense.__mapper__.relationships["vendor"]
    expense_lines = Expense.__mapper__.relationships["lines"]
    line_expense = ExpenseLine.__mapper__.relationships["expense"]

    assert isinstance(vendor_expenses, RelationshipProperty)
    assert isinstance(expense_vendor, RelationshipProperty)
    assert isinstance(expense_lines, RelationshipProperty)
    assert isinstance(line_expense, RelationshipProperty)
    assert vendor_expenses.uselist is True
    assert expense_vendor.uselist is False
    assert expense_lines.uselist is True
    assert line_expense.uselist is False


def test_vendor_code_unique_per_business() -> None:
    """Vendor codes are unique per business."""
    assert ("business_id", "vendor_code") in unique_constraint_sets(Vendor)


def test_expense_number_unique_per_business() -> None:
    """Expense numbers are unique per business."""
    assert ("business_id", "expense_number") in unique_constraint_sets(Expense)


def test_expense_enum_values() -> None:
    """Expense enums expose expected lifecycle and category values."""
    assert ExpenseStatus.DRAFT.value == "draft"
    assert ExpenseStatus.APPROVED.value == "approved"
    assert ExpenseStatus.PAID.value == "paid"
    assert ExpenseStatus.CANCELLED.value == "cancelled"
    assert ExpenseCategory.TRAVEL.value == "travel"
    assert ExpenseCategory.OFFICE.value == "office"
    assert ExpenseCategory.RENT.value == "rent"
    assert ExpenseCategory.UTILITIES.value == "utilities"
    assert ExpenseCategory.MARKETING.value == "marketing"
    assert ExpenseCategory.SALARY.value == "salary"
    assert ExpenseCategory.PROFESSIONAL_FEES.value == "professional_fees"
    assert ExpenseCategory.SOFTWARE.value == "software"
    assert ExpenseCategory.HARDWARE.value == "hardware"
    assert ExpenseCategory.OTHER.value == "other"
