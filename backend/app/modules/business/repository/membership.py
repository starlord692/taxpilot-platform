"""Business membership repository."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.repositories import BaseRepository
from app.modules.business.models import BusinessMembership

OWNER_ROLE = "owner"


class BusinessMembershipRepository(BaseRepository[BusinessMembership]):
    """Repository for business membership persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, BusinessMembership)

    async def add_member(
        self,
        *,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str,
    ) -> BusinessMembership:
        """Add a member to a business."""
        membership = BusinessMembership(
            business_id=business_id,
            user_id=user_id,
            role=role,
        )
        return await self.add(membership)

    async def remove_member(self, membership: BusinessMembership) -> None:
        """Soft delete a business membership."""
        await self.delete(membership)

    async def get_members(self, business_id: uuid.UUID) -> list[BusinessMembership]:
        """Return active memberships for a business."""
        statement = (
            select(BusinessMembership)
            .where(
                BusinessMembership.business_id == business_id,
                BusinessMembership.is_deleted.is_(False),
            )
            .order_by(BusinessMembership.created_at.asc())
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_membership(
        self,
        *,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> BusinessMembership | None:
        """Return an active membership by business and user."""
        statement = select(BusinessMembership).where(
            BusinessMembership.business_id == business_id,
            BusinessMembership.user_id == user_id,
            BusinessMembership.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def is_member(self, *, business_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Return whether the user has an active business membership."""
        return (
            await self.get_membership(business_id=business_id, user_id=user_id)
            is not None
        )

    async def is_owner(self, *, business_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Return whether the user has an active owner membership."""
        membership = await self.get_membership(
            business_id=business_id,
            user_id=user_id,
        )
        return membership is not None and membership.role.lower() == OWNER_ROLE

    async def change_role(
        self,
        membership: BusinessMembership,
        *,
        role: str,
    ) -> BusinessMembership:
        """Change the role for an active business membership."""
        membership.role = role
        self.session.add(membership)
        await self.session.flush()
        return membership
