"""SQLAlchemy Unit of Work implementation."""

from collections.abc import Callable
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.unit_of_work.interface import UnitOfWork
from app.modules.identity.repository import (
    IdentityPermissionRepository,
    IdentityRefreshTokenRepository,
    IdentityRoleRepository,
    IdentityUserRepository,
)

SessionFactory = Callable[[], AsyncSession]


class SQLAlchemyUnitOfWork(UnitOfWork):
    """Coordinate repositories inside a single SQLAlchemy transaction."""

    def __init__(self, session_factory: SessionFactory) -> None:
        """Initialize with a dependency-injected async session factory."""
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._committed = False
        self.users: IdentityUserRepository
        self.roles: IdentityRoleRepository
        self.permissions: IdentityPermissionRepository
        self.refresh_tokens: IdentityRefreshTokenRepository

    async def __aenter__(self) -> Self:
        """Open a session and bind repositories to the transaction scope."""
        self._session = self._session_factory()
        self._committed = False
        self.users = IdentityUserRepository(self._session)
        self.roles = IdentityRoleRepository(self._session)
        self.permissions = IdentityPermissionRepository(self._session)
        self.refresh_tokens = IdentityRefreshTokenRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Rollback uncommitted work on exit and always close the session."""
        try:
            if exc_type is not None or not self._committed:
                await self.rollback()
        finally:
            if self._session is not None:
                await self._session.close()
                self._session = None

    async def commit(self) -> None:
        """Commit the current transaction."""
        session = self._get_session()
        await session.commit()
        self._committed = True

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        session = self._get_session()
        await session.rollback()
        self._committed = False

    def _get_session(self) -> AsyncSession:
        """Return the active session or raise when outside a scope."""
        if self._session is None:
            raise RuntimeError("Unit of Work is not active")
        return self._session
