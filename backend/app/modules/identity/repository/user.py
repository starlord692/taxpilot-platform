"""Identity user repository."""

import uuid
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import Page, PaginationParams
from app.common.repositories import BaseRepository
from app.modules.identity.models import IdentityUser, UserStatus
from app.modules.identity.schemas import CreateUserRequest, UpdateUserRequest


class IdentityUserRepository(BaseRepository[IdentityUser]):
    """Repository for identity user persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, IdentityUser)

    async def create_user(self, request: CreateUserRequest) -> IdentityUser:
        """Create an identity user without handling credentials."""
        display_name = request.display_name or (
            f"{request.first_name} {request.last_name}"
        )
        user = IdentityUser(
            email=request.email,
            first_name=request.first_name,
            last_name=request.last_name,
            display_name=display_name,
            status=UserStatus.PENDING,
            failed_login_attempts=0,
        )
        return await self.add(user)

    async def get_by_id(self, user_id: uuid.UUID) -> IdentityUser | None:
        """Return a non-deleted user by UUID."""
        statement = select(IdentityUser).where(
            IdentityUser.id == user_id,
            IdentityUser.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> IdentityUser | None:
        """Return a non-deleted user by normalized email."""
        statement = select(IdentityUser).where(
            IdentityUser.email == email.lower(),
            IdentityUser.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def exists_by_email(self, email: str) -> bool:
        """Return whether a non-deleted user exists by email."""
        return await self.get_by_email(email) is not None

    async def update_user(
        self,
        user: IdentityUser,
        request: UpdateUserRequest,
    ) -> IdentityUser:
        """Update mutable user fields from a request schema."""
        update_data = request.model_dump(exclude_unset=True)
        for field_name, value in update_data.items():
            setattr(user, field_name, value)
        self.session.add(user)
        await self.session.flush()
        return user

    async def soft_delete(self, user: IdentityUser) -> None:
        """Soft delete an identity user."""
        await self.delete(user)

    async def list_users(
        self,
        pagination: PaginationParams | None = None,
    ) -> Page[IdentityUser]:
        """Return paginated non-deleted users."""
        params = pagination or PaginationParams()
        statement = (
            select(IdentityUser)
            .where(IdentityUser.is_deleted.is_(False))
            .order_by(IdentityUser.created_at.desc())
        )
        total_statement = select(IdentityUser).where(
            IdentityUser.is_deleted.is_(False)
        )
        total = await self.count_statement(total_statement)
        result = await self.session.execute(
            statement.offset(params.offset).limit(params.limit)
        )
        return Page.create(
            items=list(result.scalars().all()),
            total=total,
            params=params,
        )

    async def lock_user(
        self,
        user: IdentityUser,
        *,
        locked_until: datetime | None,
    ) -> IdentityUser:
        """Lock a user until the provided timestamp."""
        user.status = UserStatus.LOCKED
        user.locked_until = locked_until
        self.session.add(user)
        await self.session.flush()
        return user

    async def unlock_user(self, user: IdentityUser) -> IdentityUser:
        """Unlock a user and clear the lock timestamp."""
        user.status = UserStatus.ACTIVE
        user.locked_until = None
        self.session.add(user)
        await self.session.flush()
        return user

    async def increment_failed_login(self, user: IdentityUser) -> IdentityUser:
        """Increment failed login attempts for a user."""
        user.failed_login_attempts += 1
        self.session.add(user)
        await self.session.flush()
        return user

    async def reset_failed_login(self, user: IdentityUser) -> IdentityUser:
        """Reset failed login attempts for a user."""
        user.failed_login_attempts = 0
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_last_login(
        self,
        user: IdentityUser,
        *,
        login_at: datetime,
    ) -> IdentityUser:
        """Update the user's last login timestamp."""
        user.last_login_at = login_at
        self.session.add(user)
        await self.session.flush()
        return user

    async def count_statement(self, statement: Select[tuple[IdentityUser]]) -> int:
        """Count rows from a selectable statement."""
        count_statement = select(func.count()).select_from(statement.subquery())
        result = await self.session.execute(count_statement)
        return int(result.scalar_one())
