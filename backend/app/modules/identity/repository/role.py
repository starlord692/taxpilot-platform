"""Identity role repository."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.repositories import BaseRepository
from app.modules.identity.models import IdentityRole, IdentityUserRole


class IdentityRoleRepository(BaseRepository[IdentityRole]):
    """Repository for identity role persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, IdentityRole)

    async def create_role(
        self,
        *,
        name: str,
        description: str | None = None,
        is_system: bool = False,
    ) -> IdentityRole:
        """Create an identity role."""
        role = IdentityRole(
            name=name,
            description=description,
            is_system=is_system,
        )
        return await self.add(role)

    async def assign_role(
        self,
        *,
        user_id: uuid.UUID,
        role_id: uuid.UUID,
        assigned_by: uuid.UUID | None = None,
    ) -> IdentityUserRole:
        """Assign a role to a user."""
        assignment = IdentityUserRole(
            user_id=user_id,
            role_id=role_id,
            assigned_by=assigned_by,
        )
        self.session.add(assignment)
        await self.session.flush()
        return assignment

    async def remove_role(self, assignment: IdentityUserRole) -> None:
        """Remove a user-role assignment."""
        await self.session.delete(assignment)
        await self.session.flush()

    async def get_roles(self, user_id: uuid.UUID) -> list[IdentityRole]:
        """Return roles assigned to a user."""
        statement = (
            select(IdentityRole)
            .join(IdentityUserRole, IdentityUserRole.role_id == IdentityRole.id)
            .where(IdentityUserRole.user_id == user_id)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def role_exists(self, name: str) -> bool:
        """Return whether a role exists by name."""
        return await self.get_by_name(name) is not None

    async def get_by_name(self, name: str) -> IdentityRole | None:
        """Return a role by name."""
        statement = select(IdentityRole).where(IdentityRole.name == name)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()
