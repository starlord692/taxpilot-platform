"""Tests for General Ledger database model mappings."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import RelationshipProperty, configure_mappers

from app.modules.accounting.ledger.models import (
    GeneralLedgerEntry,
    LedgerEntryType,
)


def test_ledger_entry_creation() -> None:
    """Ledger entries can be constructed with expected immutable fields."""
    business_id = uuid.uuid4()
    journal_entry_id = uuid.uuid4()
    journal_line_id = uuid.uuid4()
    account_id = uuid.uuid4()

    entry = GeneralLedgerEntry(
        business_id=business_id,
        journal_entry_id=journal_entry_id,
        journal_line_id=journal_line_id,
        account_id=account_id,
        transaction_date=date(2026, 4, 1),
        posting_date=date(2026, 4, 2),
        debit=Decimal("250.00"),
        credit=Decimal("0.00"),
        description="Posted cash receipt",
    )

    assert entry.business_id == business_id
    assert entry.journal_entry_id == journal_entry_id
    assert entry.journal_line_id == journal_line_id
    assert entry.account_id == account_id
    assert entry.transaction_date == date(2026, 4, 1)
    assert entry.posting_date == date(2026, 4, 2)
    assert entry.debit == Decimal("250.00")
    assert entry.credit == Decimal("0.00")
    assert entry.running_balance is None


def test_ledger_relationships() -> None:
    """Ledger entries relate to business, journal, line, and account."""
    configure_mappers()

    business_relationship = GeneralLedgerEntry.__mapper__.relationships["business"]
    journal_relationship = GeneralLedgerEntry.__mapper__.relationships[
        "journal_entry"
    ]
    line_relationship = GeneralLedgerEntry.__mapper__.relationships["journal_line"]
    account_relationship = GeneralLedgerEntry.__mapper__.relationships["account"]

    assert isinstance(business_relationship, RelationshipProperty)
    assert isinstance(journal_relationship, RelationshipProperty)
    assert isinstance(line_relationship, RelationshipProperty)
    assert isinstance(account_relationship, RelationshipProperty)
    assert business_relationship.uselist is False
    assert journal_relationship.uselist is False
    assert line_relationship.uselist is False
    assert account_relationship.uselist is False


def test_ledger_business_isolation_field() -> None:
    """Ledger entries are scoped to a single business."""
    business_id = uuid.uuid4()
    entry = GeneralLedgerEntry(
        business_id=business_id,
        journal_entry_id=uuid.uuid4(),
        journal_line_id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        transaction_date=date(2026, 4, 1),
        posting_date=date(2026, 4, 1),
        debit=Decimal("0.00"),
        credit=Decimal("125.00"),
    )

    assert entry.business_id == business_id


def test_ledger_source_fields() -> None:
    """Ledger entries retain source module metadata."""
    source_id = uuid.uuid4()
    entry = GeneralLedgerEntry(
        business_id=uuid.uuid4(),
        journal_entry_id=uuid.uuid4(),
        journal_line_id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        transaction_date=date(2026, 4, 1),
        posting_date=date(2026, 4, 1),
        debit=Decimal("100.00"),
        credit=Decimal("0.00"),
        source_module="journal",
        source_entity="journal_entry",
        source_entity_id=source_id,
    )

    assert entry.source_module == "journal"
    assert entry.source_entity == "journal_entry"
    assert entry.source_entity_id == source_id


def test_ledger_entry_type_enum_values() -> None:
    """Ledger entry side enum exposes expected values."""
    assert LedgerEntryType.DEBIT.value == "debit"
    assert LedgerEntryType.CREDIT.value == "credit"
