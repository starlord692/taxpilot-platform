"""Tests for account balance model mappings."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from sqlalchemy import Table, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, RelationshipProperty, configure_mappers

from app.modules.accounting.balances.models import AccountBalance


def unique_constraint_sets(model: type[DeclarativeBase]) -> set[tuple[str, ...]]:
    """Return unique constraint column names for a mapped model."""
    table = cast(Table, model.__table__)
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_create_account_balance() -> None:
    """Account balance can be constructed with expected fields."""
    business_id = uuid.uuid4()
    account_id = uuid.uuid4()
    last_posted_at = datetime(2026, 4, 1, tzinfo=UTC)
    balance = AccountBalance(
        business_id=business_id,
        account_id=account_id,
        current_debit=Decimal("250.00"),
        current_credit=Decimal("100.00"),
        current_balance=Decimal("150.00"),
        last_posted_at=last_posted_at,
    )

    assert balance.business_id == business_id
    assert balance.account_id == account_id
    assert balance.current_debit == Decimal("250.00")
    assert balance.current_credit == Decimal("100.00")
    assert balance.current_balance == Decimal("150.00")
    assert balance.last_posted_at == last_posted_at


def test_one_balance_row_per_account() -> None:
    """Account balances enforce one row per account."""
    assert ("account_id",) in unique_constraint_sets(AccountBalance)


def test_account_balance_relationships() -> None:
    """Account balances relate to business and account."""
    configure_mappers()

    business_relationship = AccountBalance.__mapper__.relationships["business"]
    account_relationship = AccountBalance.__mapper__.relationships["account"]

    assert isinstance(business_relationship, RelationshipProperty)
    assert isinstance(account_relationship, RelationshipProperty)
    assert business_relationship.uselist is False
    assert account_relationship.uselist is False
