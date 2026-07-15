"""Identity permission repository."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.repositories import BaseRepository
from app.modules.identity.models import (
    IdentityPermission,
    IdentityRolePermission,
)


class IdentityPermissionRepository(BaseRepository[IdentityPermission]):
    """Repository for identity permission persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, IdentityPermission)

    async def create_permission(
        self,
        *,
        name: str,
        description: str | None = None,
    ) -> IdentityPermission:
        """Create an identity permission."""
        permission = IdentityPermission(name=name, description=description)
        return await self.add(permission)

    async def assign_permission(
        self,
        *,
        role_id: uuid.UUID,
        permission_id: uuid.UUID,
    ) -> IdentityRolePermission:
        """Assign a permission to a role."""
        assignment = IdentityRolePermission(
            role_id=role_id,
            permission_id=permission_id,
        )
        self.session.add(assignment)
        await self.session.flush()
        return assignment

    async def remove_permission(self, assignment: IdentityRolePermission) -> None:
        """Remove a role-permission assignment."""
        await self.session.delete(assignment)
        await self.session.flush()

    async def list_permissions(self, role_id: uuid.UUID) -> list[IdentityPermission]:
        """Return permissions assigned to a role."""
        statement = (
            select(IdentityPermission)
            .join(
                IdentityRolePermission,
                IdentityRolePermission.permission_id == IdentityPermission.id,
            )
            .where(IdentityRolePermission.role_id == role_id)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())
