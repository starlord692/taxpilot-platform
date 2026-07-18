"""Tests for identity database model mappings."""

from collections.abc import Iterable
from typing import cast

from sqlalchemy import Table, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, RelationshipProperty, configure_mappers

from app.modules.identity.models import (
    IdentityCredential,
    IdentityPermission,
    IdentityRole,
    IdentityRolePermission,
    IdentityUser,
    IdentityUserRole,
    UserStatus,
)


def unique_columns(model: type[DeclarativeBase]) -> set[str]:
    """Return single-column unique columns for a mapped model."""
    table = cast(Table, model.__table__)
    return {column.name for column in table.columns if column.unique}


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


def test_identity_user_email_is_unique_and_lowercase_normalized() -> None:
    """Identity user email is unique and normalized by the model."""
    user = IdentityUser(
        email="OWNER@EXAMPLE.COM",
        first_name="Tax",
        last_name="Pilot",
        display_name="Tax Pilot",
    )

    assert "email" in unique_columns(IdentityUser)
    assert user.email == "owner@example.com"
    assert IdentityUser.__table__.c.status.default is not None
    assert IdentityUser.__table__.c.status.default.arg == UserStatus.PENDING


def test_identity_credential_has_one_to_one_user_relationship() -> None:
    """Identity credentials are mapped one-to-one with users."""
    configure_mappers()

    user_relationship = IdentityUser.__mapper__.relationships["credential"]
    credential_relationship = IdentityCredential.__mapper__.relationships["user"]

    assert isinstance(user_relationship, RelationshipProperty)
    assert isinstance(credential_relationship, RelationshipProperty)
    assert user_relationship.uselist is False
    assert credential_relationship.uselist is False
    assert "user_id" in unique_columns(IdentityCredential)


def test_identity_role_name_is_unique() -> None:
    """Identity role names are unique."""
    assert "name" in unique_columns(IdentityRole)


def test_identity_permission_name_is_unique() -> None:
    """Identity permission names are unique."""
    assert "name" in unique_columns(IdentityPermission)


def test_identity_user_role_pair_is_unique() -> None:
    """Identity user-role assignments are unique by pair."""
    assert ("user_id", "role_id") in unique_constraint_sets(IdentityUserRole)


def test_identity_role_permission_pair_is_unique() -> None:
    """Identity role-permission assignments are unique by pair."""
    assert ("role_id", "permission_id") in unique_constraint_sets(
        IdentityRolePermission
    )
