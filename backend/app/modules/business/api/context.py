"""Shared authenticated business-context resolution."""

import uuid
from dataclasses import dataclass
from typing import Protocol

from app.modules.business.exceptions import (
    BusinessArchivedException,
    BusinessNotFoundException,
    BusinessNotMemberException,
)
from app.modules.business.models import Business, BusinessMembership, BusinessStatus
from app.modules.identity.models import IdentityUser


class BusinessContextBusinessRepository(Protocol):
    """Business repository behavior required by context resolution."""

    async def get_by_id(self, business_id: uuid.UUID) -> Business | None:
        """Return a non-deleted business by UUID."""
        ...


class BusinessContextMembershipRepository(Protocol):
    """Membership repository behavior required by context resolution."""

    async def get_membership(
        self,
        *,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> BusinessMembership | None:
        """Return an active membership for a business and user."""
        ...


class BusinessContextUnitOfWork(Protocol):
    """Unit of Work contract required by business-context resolution."""

    businesses: BusinessContextBusinessRepository
    business_memberships: BusinessContextMembershipRepository

    async def __aenter__(self) -> "BusinessContextUnitOfWork":
        """Enter transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit transaction scope."""
        ...


@dataclass(frozen=True)
class BusinessContext:
    """Resolved authenticated tenant context."""

    business: Business
    membership: BusinessMembership
    user: IdentityUser

    @property
    def business_id(self) -> uuid.UUID:
        """Return the resolved business UUID."""
        return self.business.id

    @property
    def user_id(self) -> uuid.UUID:
        """Return the authenticated user UUID."""
        return self.user.id


async def resolve_business_context(
    uow: BusinessContextUnitOfWork,
    *,
    business_id: uuid.UUID,
    current_user: IdentityUser,
    entered: bool = False,
) -> BusinessContext:
    """Resolve and validate the authenticated user's active business context."""
    if not entered:
        async with uow:
            return await resolve_business_context(
                uow,
                business_id=business_id,
                current_user=current_user,
                entered=True,
            )

    business = await uow.businesses.get_by_id(business_id)
    if business is None:
        raise BusinessNotFoundException(
            "Business not found",
            details={"business_id": str(business_id)},
        )
    if business.status != BusinessStatus.ACTIVE:
        raise BusinessArchivedException(
            "Business is not active",
            details={
                "business_id": str(business_id),
                "status": business.status.value,
            },
        )

    membership = await uow.business_memberships.get_membership(
        business_id=business_id,
        user_id=current_user.id,
    )
    if membership is None:
        raise BusinessNotMemberException(
            "User is not a member of the business",
            details={
                "business_id": str(business_id),
                "user_id": str(current_user.id),
            },
        )

    return BusinessContext(
        business=business,
        membership=membership,
        user=current_user,
    )


async def ensure_business_context(
    uow: BusinessContextUnitOfWork,
    *,
    business_id: uuid.UUID,
    current_user: IdentityUser,
    entered: bool = False,
) -> None:
    """Validate business context when the caller does not need the result."""
    await resolve_business_context(
        uow,
        business_id=business_id,
        current_user=current_user,
        entered=entered,
    )


async def ensure_active_business_membership(
    uow: BusinessContextUnitOfWork,
    *,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
    entered: bool = False,
) -> None:
    """Validate an active business and active membership by authenticated user id."""
    if not entered:
        async with uow:
            await ensure_active_business_membership(
                uow,
                business_id=business_id,
                user_id=user_id,
                entered=True,
            )
            return

    business = await uow.businesses.get_by_id(business_id)
    if business is None:
        raise BusinessNotFoundException(
            "Business not found",
            details={"business_id": str(business_id)},
        )
    if business.status != BusinessStatus.ACTIVE:
        raise BusinessArchivedException(
            "Business is not active",
            details={
                "business_id": str(business_id),
                "status": business.status.value,
            },
        )

    membership = await uow.business_memberships.get_membership(
        business_id=business_id,
        user_id=user_id,
    )
    if membership is None:
        raise BusinessNotMemberException(
            "User is not a member of the business",
            details={
                "business_id": str(business_id),
                "user_id": str(user_id),
            },
        )
