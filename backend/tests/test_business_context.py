"""Tests for shared authenticated business-context resolution."""

import uuid
from typing import Self, cast

import pytest

from app.modules.business.api.context import (
    BusinessContextUnitOfWork,
    ensure_active_business_membership,
    resolve_business_context,
)
from app.modules.business.exceptions import (
    BusinessArchivedException,
    BusinessNotFoundException,
    BusinessNotMemberException,
)
from app.modules.business.models import (
    Business,
    BusinessMembership,
    BusinessStatus,
    BusinessType,
    RegistrationStatus,
)
from app.modules.identity.models import IdentityUser, UserStatus


class FakeBusinessRepository:
    """Fake business repository for context resolution tests."""

    def __init__(self, business: Business | None) -> None:
        """Initialize fake business lookup."""
        self.business = business

    async def get_by_id(self, business_id: uuid.UUID) -> Business | None:
        """Return the configured business when IDs match."""
        if self.business is None or self.business.id != business_id:
            return None
        return self.business


class FakeMembershipRepository:
    """Fake membership repository for context resolution tests."""

    def __init__(self, membership: BusinessMembership | None) -> None:
        """Initialize fake membership lookup."""
        self.membership = membership

    async def get_membership(
        self,
        *,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> BusinessMembership | None:
        """Return the configured membership when IDs match."""
        if (
            self.membership is None
            or self.membership.business_id != business_id
            or self.membership.user_id != user_id
        ):
            return None
        return self.membership


class FakeBusinessUnitOfWork:
    """Fake Unit of Work used by shared resolver tests."""

    def __init__(
        self,
        *,
        business: Business | None,
        membership: BusinessMembership | None,
    ) -> None:
        """Initialize fake repositories."""
        self.businesses = FakeBusinessRepository(business)
        self.business_memberships = FakeMembershipRepository(membership)
        self.entered = False

    async def __aenter__(self) -> Self:
        """Enter fake transaction scope."""
        self.entered = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit fake transaction scope."""
        _ = exc_type
        _ = exc
        _ = traceback


def build_user() -> IdentityUser:
    """Build authenticated user."""
    return IdentityUser(
        id=uuid.uuid4(),
        email="owner@example.com",
        first_name="Aarav",
        last_name="Sharma",
        display_name="Aarav Sharma",
        status=UserStatus.ACTIVE,
    )


def build_business(
    business_id: uuid.UUID,
    *,
    status: BusinessStatus = BusinessStatus.ACTIVE,
) -> Business:
    """Build business model for context tests."""
    return Business(
        id=business_id,
        legal_name="Aarav Technologies Private Limited",
        business_type=BusinessType.PRIVATE_LIMITED,
        registration_status=RegistrationStatus.REGISTERED,
        status=status,
    )


def build_membership(
    *,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
) -> BusinessMembership:
    """Build business membership model for context tests."""
    return BusinessMembership(
        id=uuid.uuid4(),
        business_id=business_id,
        user_id=user_id,
        role="member",
    )


def as_context_uow(uow: FakeBusinessUnitOfWork) -> BusinessContextUnitOfWork:
    """Cast the fake to the resolver protocol used by production UOWs."""
    return cast(BusinessContextUnitOfWork, uow)


@pytest.mark.asyncio
async def test_resolve_business_context_for_active_member() -> None:
    """Active businesses with active membership resolve successfully."""
    user = build_user()
    business = build_business(uuid.uuid4())
    membership = build_membership(business_id=business.id, user_id=user.id)
    uow = FakeBusinessUnitOfWork(business=business, membership=membership)

    context = await resolve_business_context(
        as_context_uow(uow),
        business_id=business.id,
        current_user=user,
    )

    assert context.business_id == business.id
    assert context.user_id == user.id
    assert context.membership == membership
    assert uow.entered is True


@pytest.mark.asyncio
async def test_business_context_rejects_missing_business() -> None:
    """Missing or soft-deleted businesses are rejected as not found."""
    user = build_user()
    business_id = uuid.uuid4()
    uow = FakeBusinessUnitOfWork(business=None, membership=None)

    with pytest.raises(BusinessNotFoundException):
        await ensure_active_business_membership(
            as_context_uow(uow),
            business_id=business_id,
            user_id=user.id,
        )


@pytest.mark.asyncio
async def test_business_context_rejects_inactive_business() -> None:
    """Inactive or archived businesses cannot be used as active context."""
    user = build_user()
    business = build_business(uuid.uuid4(), status=BusinessStatus.INACTIVE)
    membership = build_membership(business_id=business.id, user_id=user.id)
    uow = FakeBusinessUnitOfWork(business=business, membership=membership)

    with pytest.raises(BusinessArchivedException):
        await ensure_active_business_membership(
            as_context_uow(uow),
            business_id=business.id,
            user_id=user.id,
        )


@pytest.mark.asyncio
async def test_business_context_rejects_missing_membership() -> None:
    """Users without active membership cannot resolve business context."""
    user = build_user()
    business = build_business(uuid.uuid4())
    uow = FakeBusinessUnitOfWork(business=business, membership=None)

    with pytest.raises(BusinessNotMemberException):
        await ensure_active_business_membership(
            as_context_uow(uow),
            business_id=business.id,
            user_id=user.id,
        )
