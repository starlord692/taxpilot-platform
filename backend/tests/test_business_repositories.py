"""Tests for business repositories."""

import uuid
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PaginationParams
from app.modules.business.models import (
    Business,
    BusinessAddress,
    BusinessMembership,
    BusinessSettings,
    BusinessStatus,
    BusinessTaxProfile,
    BusinessType,
)
from app.modules.business.repository import (
    BusinessMembershipRepository,
    BusinessRepository,
)
from app.modules.business.schemas import CreateBusinessRequest, UpdateBusinessRequest

pytestmark = pytest.mark.asyncio
EXPECTED_DOUBLE_FLUSHES = 2


class ScalarCollection:
    """Simple scalar collection test double."""

    def __init__(self, items: list[Any]) -> None:
        """Initialize with scalar items."""
        self._items = items

    def all(self) -> list[Any]:
        """Return scalar items."""
        return self._items

    def unique(self) -> "ScalarCollection":
        """Return unique scalar collection."""
        return self


class ExecuteResult:
    """Simple async session execute result test double."""

    def __init__(
        self,
        *,
        one_or_none: Any = None,
        one: int = 0,
        items: list[Any] | None = None,
    ) -> None:
        """Initialize result values."""
        self._one_or_none = one_or_none
        self._one = one
        self._items = items or []

    def scalar_one_or_none(self) -> Any:
        """Return one scalar value or none."""
        return self._one_or_none

    def scalar_one(self) -> int:
        """Return one scalar integer value."""
        return self._one

    def scalars(self) -> ScalarCollection:
        """Return scalar collection."""
        return ScalarCollection(self._items)


def build_session_mock() -> AsyncSession:
    """Build an async session mock for repository tests."""
    session = Mock(spec=AsyncSession)
    session.add = Mock()
    session.delete = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return cast(AsyncSession, session)


def build_create_business_request() -> CreateBusinessRequest:
    """Build a valid create business request."""
    return CreateBusinessRequest(
        legal_name="TaxPilot Labs Private Limited",
        trade_name="TaxPilot Labs",
        business_type=BusinessType.PRIVATE_LIMITED,
        business_email="accounts@example.com",
        business_phone="+919876543210",
        website="https://example.com",
        address={
            "address_line_1": "42 Residency Road",
            "city": "Bengaluru",
            "state": "Karnataka",
            "country": "India",
            "postal_code": "560025",
        },
        tax_profile={
            "gstin": "29ABCDE1234F1Z5",
            "pan": "ABCDE1234F",
            "financial_year_start": "2026-04-01",
            "gst_registered": True,
            "composition_scheme": False,
        },
        settings={
            "currency": "INR",
            "timezone": "Asia/Kolkata",
            "date_format": "DD/MM/YYYY",
            "language": "en",
        },
    )


def build_business() -> Business:
    """Build a business model."""
    return Business(
        legal_name="TaxPilot Labs Private Limited",
        trade_name="TaxPilot Labs",
        business_type=BusinessType.PRIVATE_LIMITED,
        status=BusinessStatus.ACTIVE,
    )


async def test_create_business_adds_business_aggregate() -> None:
    """Business repository creates a business with nested records."""
    session = build_session_mock()
    repository = BusinessRepository(session)

    business = await repository.create_business(
        build_create_business_request(),
        business_code="BUS-001",
    )

    assert isinstance(business, Business)
    assert business.business_code == "BUS-001"
    assert business.legal_name == "TaxPilot Labs Private Limited"
    assert isinstance(business.address, BusinessAddress)
    assert isinstance(business.tax_profile, BusinessTaxProfile)
    assert isinstance(business.settings, BusinessSettings)
    cast(Any, session.add).assert_called_once_with(business)
    cast(Any, session.flush).assert_awaited_once()


async def test_get_by_id_and_business_code_return_business() -> None:
    """Business lookup methods return matching business records."""
    session = build_session_mock()
    business = build_business()
    cast(Any, session.execute).return_value = ExecuteResult(one_or_none=business)
    repository = BusinessRepository(session)

    assert await repository.get_by_id(uuid.uuid4()) is business
    assert await repository.get_by_business_code("BUS-001") is business


async def test_update_business_mutates_scalar_fields() -> None:
    """Business repository updates mutable scalar fields."""
    session = build_session_mock()
    repository = BusinessRepository(session)
    business = build_business()

    result = await repository.update_business(
        business,
        UpdateBusinessRequest(trade_name="TaxPilot", website="https://taxpilot.ai"),
    )

    assert result is business
    assert business.trade_name == "TaxPilot"
    assert business.website == "https://taxpilot.ai"
    cast(Any, session.flush).assert_awaited_once()


async def test_archive_and_restore_business_update_status() -> None:
    """Business repository archives and restores businesses."""
    session = build_session_mock()
    repository = BusinessRepository(session)
    business = build_business()

    await repository.archive_business(business)
    assert business.status == BusinessStatus.ARCHIVED

    await repository.restore_business(business)
    assert business.status.value == BusinessStatus.ACTIVE.value
    assert cast(Any, session.flush).await_count == EXPECTED_DOUBLE_FLUSHES


async def test_exists_checks_return_true() -> None:
    """Business repository existence checks use lookup queries."""
    session = build_session_mock()
    cast(Any, session.execute).return_value = ExecuteResult(one_or_none=uuid.uuid4())
    repository = BusinessRepository(session)

    assert await repository.exists_by_name("TaxPilot Labs Private Limited") is True
    assert await repository.exists_by_email("ACCOUNTS@EXAMPLE.COM") is True
    assert await repository.exists_by_gstin("29abcde1234f1z5") is True


async def test_get_tax_profile_and_settings_return_records() -> None:
    """Business repository returns one-to-one child records."""
    session = build_session_mock()
    tax_profile = BusinessTaxProfile(
        business_id=uuid.uuid4(),
        financial_year_start="2026-04-01",
    )
    settings = BusinessSettings(business_id=uuid.uuid4())
    cast(Any, session.execute).side_effect = [
        ExecuteResult(one_or_none=tax_profile),
        ExecuteResult(one_or_none=settings),
    ]
    repository = BusinessRepository(session)

    assert await repository.get_tax_profile(uuid.uuid4()) is tax_profile
    assert await repository.get_settings(uuid.uuid4()) is settings


async def test_list_by_user_returns_paginated_businesses() -> None:
    """Business repository returns paginated businesses by user membership."""
    session = build_session_mock()
    business = build_business()
    cast(Any, session.execute).return_value = ExecuteResult(items=[business])
    repository = BusinessRepository(session)
    cast(Any, repository).count_statement = AsyncMock(return_value=1)

    page = await repository.list_by_user(
        uuid.uuid4(),
        PaginationParams(page=1, size=10),
    )

    assert page.items == [business]
    assert page.meta.total == 1
    assert page.meta.page == 1


async def test_add_and_remove_member() -> None:
    """Membership repository creates and soft-deletes memberships."""
    session = build_session_mock()
    repository = BusinessMembershipRepository(session)
    business_id = uuid.uuid4()
    user_id = uuid.uuid4()

    membership = await repository.add_member(
        business_id=business_id,
        user_id=user_id,
        role="owner",
    )
    await repository.remove_member(membership)

    assert isinstance(membership, BusinessMembership)
    assert membership.business_id == business_id
    assert membership.user_id == user_id
    assert membership.is_deleted is True
    assert cast(Any, session.flush).await_count == EXPECTED_DOUBLE_FLUSHES


async def test_membership_lookup_methods() -> None:
    """Membership repository returns memberships and booleans."""
    session = build_session_mock()
    membership = BusinessMembership(
        business_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        role="owner",
    )
    cast(Any, session.execute).return_value = ExecuteResult(
        one_or_none=membership,
        items=[membership],
    )
    repository = BusinessMembershipRepository(session)

    assert await repository.get_members(membership.business_id) == [membership]
    assert (
        await repository.get_membership(
            business_id=membership.business_id,
            user_id=membership.user_id,
        )
        is membership
    )
    assert (
        await repository.is_member(
            business_id=membership.business_id,
            user_id=membership.user_id,
        )
        is True
    )
    assert (
        await repository.is_owner(
            business_id=membership.business_id,
            user_id=membership.user_id,
        )
        is True
    )


async def test_change_role_updates_membership() -> None:
    """Membership repository updates membership role."""
    session = build_session_mock()
    repository = BusinessMembershipRepository(session)
    membership = BusinessMembership(
        business_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        role="member",
    )

    result = await repository.change_role(membership, role="admin")

    assert result is membership
    assert membership.role == "admin"
    cast(Any, session.flush).assert_awaited_once()
