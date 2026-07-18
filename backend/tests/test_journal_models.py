"""Tests for journal entry database model mappings."""

import uuid
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import cast

from sqlalchemy import Table, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, RelationshipProperty, configure_mappers

from app.modules.accounting.journal.models import (
    JournalEntry,
    JournalEntryLine,
    JournalStatus,
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


def test_create_journal_entry() -> None:
    """Journal entry can be constructed with expected fields and defaults."""
    business_id = uuid.uuid4()
    created_by = uuid.uuid4()
    journal = JournalEntry(
        business_id=business_id,
        journal_number="JV-0001",
        transaction_date=date(2026, 4, 1),
        posting_date=date(2026, 4, 1),
        reference="INV-0001",
        description="Opening journal",
        created_by=created_by,
    )

    assert journal.business_id == business_id
    assert journal.journal_number == "JV-0001"
    assert journal.transaction_date == date(2026, 4, 1)
    assert journal.created_by == created_by
    assert JournalEntry.__table__.c.status.default is not None
    assert JournalEntry.__table__.c.status.default.arg == JournalStatus.DRAFT


def test_journal_entry_lines() -> None:
    """Journal entry lines hold debit and credit values."""
    journal_entry_id = uuid.uuid4()
    debit_line = JournalEntryLine(
        journal_entry_id=journal_entry_id,
        account_id=uuid.uuid4(),
        debit=Decimal("100.00"),
        credit=Decimal("0.00"),
        description="Debit cash",
    )
    credit_line = JournalEntryLine(
        journal_entry_id=journal_entry_id,
        account_id=uuid.uuid4(),
        debit=Decimal("0.00"),
        credit=Decimal("100.00"),
        description="Credit capital",
    )

    assert debit_line.debit == Decimal("100.00")
    assert debit_line.credit == Decimal("0.00")
    assert credit_line.debit == Decimal("0.00")
    assert credit_line.credit == Decimal("100.00")


def test_journal_entry_line_relationships() -> None:
    """Journal entries have many lines."""
    configure_mappers()

    lines_relationship = JournalEntry.__mapper__.relationships["lines"]
    entry_relationship = JournalEntryLine.__mapper__.relationships["journal_entry"]

    assert isinstance(lines_relationship, RelationshipProperty)
    assert isinstance(entry_relationship, RelationshipProperty)
    assert lines_relationship.uselist is True
    assert entry_relationship.uselist is False


def test_journal_relationships() -> None:
    """Journal models relate to business and account models."""
    configure_mappers()

    business_relationship = JournalEntry.__mapper__.relationships["business"]
    account_relationship = JournalEntryLine.__mapper__.relationships["account"]

    assert isinstance(business_relationship, RelationshipProperty)
    assert isinstance(account_relationship, RelationshipProperty)
    assert business_relationship.uselist is False
    assert account_relationship.uselist is False


def test_journal_status_enum_values() -> None:
    """Journal status enum exposes expected lifecycle values."""
    assert JournalStatus.DRAFT.value == "draft"
    assert JournalStatus.POSTED.value == "posted"
    assert JournalStatus.REVERSED.value == "reversed"


def test_journal_number_unique_within_business() -> None:
    """Journal numbers are unique per business."""
    assert ("business_id", "journal_number") in unique_constraint_sets(JournalEntry)
