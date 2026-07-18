"""Tests for chart of accounts database model mappings."""

import uuid
from collections.abc import Iterable
from typing import cast

from sqlalchemy import Table, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, RelationshipProperty, configure_mappers

from app.modules.accounting.chart_of_accounts.models import (
    Account,
    AccountCategory,
    AccountType,
    NormalBalance,
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


def unique_columns(model: type[DeclarativeBase]) -> set[str]:
    """Return single-column unique columns for a mapped model."""
    table = cast(Table, model.__table__)
    return {column.name for column in table.columns if column.unique}


def test_business_account_creation() -> None:
    """Business account can be constructed with expected fields and defaults."""
    business_id = uuid.uuid4()
    account_type_id = uuid.uuid4()
    account = Account(
        business_id=business_id,
        account_code="1000",
        account_name="Cash",
        account_type_id=account_type_id,
        description="Cash on hand",
    )

    assert account.business_id == business_id
    assert account.account_code == "1000"
    assert account.account_name == "Cash"
    assert account.account_type_id == account_type_id
    assert Account.__table__.c.is_system.default is not None
    assert Account.__table__.c.is_system.default.arg is False
    assert Account.__table__.c.is_active.default is not None
    assert Account.__table__.c.is_active.default.arg is True


def test_account_codes_are_unique_within_business() -> None:
    """Account codes are unique per business."""
    assert ("business_id", "account_code") in unique_constraint_sets(Account)


def test_parent_child_account_hierarchy_relationships() -> None:
    """Accounts support self-referential parent-child hierarchy."""
    configure_mappers()

    parent_relationship = Account.__mapper__.relationships["parent_account"]
    children_relationship = Account.__mapper__.relationships["child_accounts"]

    assert isinstance(parent_relationship, RelationshipProperty)
    assert isinstance(children_relationship, RelationshipProperty)
    assert parent_relationship.uselist is False
    assert children_relationship.uselist is True


def test_account_relationships() -> None:
    """Account relationships are mapped to business and account type."""
    configure_mappers()

    business_relationship = Account.__mapper__.relationships["business"]
    account_type_relationship = Account.__mapper__.relationships["account_type"]
    type_accounts_relationship = AccountType.__mapper__.relationships["accounts"]

    assert isinstance(business_relationship, RelationshipProperty)
    assert isinstance(account_type_relationship, RelationshipProperty)
    assert isinstance(type_accounts_relationship, RelationshipProperty)
    assert business_relationship.uselist is False
    assert account_type_relationship.uselist is False
    assert type_accounts_relationship.uselist is True


def test_account_category_and_type_relationship() -> None:
    """Account categories own account types."""
    configure_mappers()

    category_relationship = AccountType.__mapper__.relationships["category"]
    account_types_relationship = AccountCategory.__mapper__.relationships[
        "account_types"
    ]

    assert isinstance(category_relationship, RelationshipProperty)
    assert isinstance(account_types_relationship, RelationshipProperty)
    assert category_relationship.uselist is False
    assert account_types_relationship.uselist is True
    assert "name" in unique_columns(AccountCategory)
    assert ("category_id", "name") in unique_constraint_sets(AccountType)


def test_normal_balance_enum_values() -> None:
    """Normal balance enum exposes debit and credit values."""
    assert NormalBalance.DEBIT.value == "debit"
    assert NormalBalance.CREDIT.value == "credit"
