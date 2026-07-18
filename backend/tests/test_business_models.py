"""Tests for business database model mappings."""

import uuid
from collections.abc import Iterable
from datetime import date
from typing import cast

from sqlalchemy import Table, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, RelationshipProperty, configure_mappers

from app.modules.business.models import (
    Business,
    BusinessAddress,
    BusinessMembership,
    BusinessSettings,
    BusinessStatus,
    BusinessTaxProfile,
    BusinessType,
    RegistrationStatus,
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


def test_business_creation_defaults() -> None:
    """Business can be constructed with expected enum defaults."""
    business = Business(
        legal_name="TaxPilot Labs Private Limited",
        trade_name="TaxPilot Labs",
        business_type=BusinessType.PRIVATE_LIMITED,
    )

    assert business.legal_name == "TaxPilot Labs Private Limited"
    assert business.trade_name == "TaxPilot Labs"
    assert business.business_type == BusinessType.PRIVATE_LIMITED
    assert Business.__table__.c.status.default is not None
    assert Business.__table__.c.status.default.arg == BusinessStatus.ACTIVE
    assert Business.__table__.c.registration_status.default is not None
    assert (
        Business.__table__.c.registration_status.default.arg
        == RegistrationStatus.PENDING
    )


def test_business_membership_pair_is_unique() -> None:
    """Business memberships are unique per business and user pair."""
    assert ("business_id", "user_id") in unique_constraint_sets(BusinessMembership)


def test_business_settings_has_one_to_one_business_relationship() -> None:
    """Business settings are mapped one-to-one with business."""
    configure_mappers()

    business_relationship = Business.__mapper__.relationships["settings"]
    settings_relationship = BusinessSettings.__mapper__.relationships["business"]

    assert isinstance(business_relationship, RelationshipProperty)
    assert isinstance(settings_relationship, RelationshipProperty)
    assert business_relationship.uselist is False
    assert settings_relationship.uselist is False
    assert "business_id" in unique_columns(BusinessSettings)


def test_business_address_has_one_to_one_business_relationship() -> None:
    """Business address is mapped one-to-one with business."""
    configure_mappers()

    business_relationship = Business.__mapper__.relationships["address"]
    address_relationship = BusinessAddress.__mapper__.relationships["business"]

    assert isinstance(business_relationship, RelationshipProperty)
    assert isinstance(address_relationship, RelationshipProperty)
    assert business_relationship.uselist is False
    assert address_relationship.uselist is False
    assert "business_id" in unique_columns(BusinessAddress)


def test_business_tax_profile_has_one_to_one_business_relationship() -> None:
    """Business tax profile is mapped one-to-one with business."""
    configure_mappers()

    business_relationship = Business.__mapper__.relationships["tax_profile"]
    tax_profile_relationship = BusinessTaxProfile.__mapper__.relationships["business"]

    assert isinstance(business_relationship, RelationshipProperty)
    assert isinstance(tax_profile_relationship, RelationshipProperty)
    assert business_relationship.uselist is False
    assert tax_profile_relationship.uselist is False
    assert "business_id" in unique_columns(BusinessTaxProfile)


def test_business_tax_profile_creation() -> None:
    """Business tax profile supports required tax fields."""
    tax_profile = BusinessTaxProfile(
        business_id=uuid.uuid4(),
        financial_year_start=date(2026, 4, 1),
        gst_registered=True,
        composition_scheme=False,
        gstin="29ABCDE1234F1Z5",
        pan="ABCDE1234F",
        tan="BLRA12345B",
    )

    assert tax_profile.financial_year_start == date(2026, 4, 1)
    assert tax_profile.gst_registered is True
    assert tax_profile.composition_scheme is False
