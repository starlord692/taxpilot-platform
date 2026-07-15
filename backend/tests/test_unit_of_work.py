"""Tests for Unit of Work infrastructure."""

from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.unit_of_work import SQLAlchemyUnitOfWork
from app.modules.identity.models import IdentityPermission, IdentityRole, IdentityUser
from app.modules.identity.repository import (
    IdentityPermissionRepository,
    IdentityRoleRepository,
    IdentityUserRepository,
)
from app.modules.identity.schemas import CreateUserRequest

pytestmark = pytest.mark.asyncio
EXPECTED_REPOSITORY_ADDS = 2


def build_session_mock() -> AsyncSession:
    """Build an async session mock for Unit of Work tests."""
    session = Mock(spec=AsyncSession)
    session.add = Mock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return cast(AsyncSession, session)


def build_create_user_request() -> CreateUserRequest:
    """Build a valid create user request."""
    return CreateUserRequest(
        email="owner@example.com",
        first_name="Jane",
        last_name="Doe",
        display_name="Jane Doe",
        password="StrongPassword123!",
    )


async def test_commit_persists_changes() -> None:
    """Commit persists repository changes through the active session."""
    session = build_session_mock()
    uow = SQLAlchemyUnitOfWork(lambda: session)

    async with uow:
        user = await uow.users.create_user(build_create_user_request())
        await uow.commit()

    assert isinstance(user, IdentityUser)
    cast(Any, session.add).assert_called_once_with(user)
    cast(Any, session.flush).assert_awaited_once()
    cast(Any, session.commit).assert_awaited_once()
    cast(Any, session.rollback).assert_not_awaited()
    cast(Any, session.close).assert_awaited_once()


async def test_rollback_discards_uncommitted_changes() -> None:
    """Exiting without commit rolls back uncommitted changes."""
    session = build_session_mock()
    uow = SQLAlchemyUnitOfWork(lambda: session)

    async with uow:
        await uow.users.create_user(build_create_user_request())

    cast(Any, session.commit).assert_not_awaited()
    cast(Any, session.rollback).assert_awaited_once()
    cast(Any, session.close).assert_awaited_once()


async def test_multiple_repository_operations_share_one_transaction() -> None:
    """Multiple repositories coordinate through the same session."""
    session = build_session_mock()
    uow = SQLAlchemyUnitOfWork(lambda: session)

    async with uow:
        role = await uow.roles.create_role(name="admin")
        permission = await uow.permissions.create_permission(
            name="identity.users.read"
        )
        await uow.commit()

    assert isinstance(role, IdentityRole)
    assert isinstance(permission, IdentityPermission)
    assert isinstance(uow.roles, IdentityRoleRepository)
    assert isinstance(uow.permissions, IdentityPermissionRepository)
    assert uow.roles.session is session
    assert uow.permissions.session is session
    assert cast(Any, session.add).call_count == EXPECTED_REPOSITORY_ADDS
    cast(Any, session.commit).assert_awaited_once()


async def test_exception_triggers_rollback() -> None:
    """Exceptions inside the context trigger rollback and close."""
    session = build_session_mock()
    uow = SQLAlchemyUnitOfWork(lambda: session)

    with pytest.raises(RuntimeError):
        async with uow:
            await uow.users.create_user(build_create_user_request())
            raise RuntimeError("boom")

    cast(Any, session.commit).assert_not_awaited()
    cast(Any, session.rollback).assert_awaited_once()
    cast(Any, session.close).assert_awaited_once()


async def test_context_manager_closes_session() -> None:
    """Context manager closes the session on exit."""
    session = build_session_mock()
    uow = SQLAlchemyUnitOfWork(lambda: session)

    async with uow:
        assert isinstance(uow.users, IdentityUserRepository)
        assert uow.users.session is session

    cast(Any, session.close).assert_awaited_once()
