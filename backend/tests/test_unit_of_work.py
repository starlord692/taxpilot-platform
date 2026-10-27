"""Tests for Unit of Work infrastructure."""

import asyncio
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
        permission = await uow.permissions.create_permission(name="identity.users.read")
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


async def test_reentrant_aenter_raises_runtime_error() -> None:
    """Entering the same UnitOfWork twice raises a descriptive RuntimeError."""
    session = build_session_mock()
    uow = SQLAlchemyUnitOfWork(lambda: session)

    async with uow:
        assert uow.is_active is True
        with pytest.raises(RuntimeError, match="Unit of Work is already active"):
            async with uow:
                pass


async def test_commit_when_inactive_raises_runtime_error() -> None:
    """Calling commit outside an active context raises RuntimeError."""
    session = build_session_mock()
    uow = SQLAlchemyUnitOfWork(lambda: session)

    with pytest.raises(RuntimeError, match="Unit of Work is not active"):
        await uow.commit()


async def test_rollback_when_inactive_raises_runtime_error() -> None:
    """Calling rollback outside an active context raises RuntimeError."""
    session = build_session_mock()
    uow = SQLAlchemyUnitOfWork(lambda: session)

    with pytest.raises(RuntimeError, match="Unit of Work is not active"):
        await uow.rollback()


async def test_commit_twice_raises_runtime_error() -> None:
    """Calling commit more than once in the same transaction raises RuntimeError."""
    session = build_session_mock()
    uow = SQLAlchemyUnitOfWork(lambda: session)

    async with uow:
        await uow.commit()
        with pytest.raises(RuntimeError, match="already been committed"):
            await uow.commit()


async def test_commit_failure_triggers_rollback_and_session_cleanup() -> None:
    """Commit failure triggers rollback and guaranteed session cleanup."""
    session = build_session_mock()
    session.commit = AsyncMock(  # type: ignore[method-assign]
        side_effect=RuntimeError("database commit failed")
    )
    uow = SQLAlchemyUnitOfWork(lambda: session)

    with pytest.raises(RuntimeError, match="database commit failed"):
        async with uow:
            await uow.commit()

    cast(Any, session.rollback).assert_awaited_once()
    cast(Any, session.close).assert_awaited_once()
    assert uow.is_active is False


async def test_task_cancellation_triggers_rollback_and_session_cleanup() -> None:
    """Task cancellation triggers rollback and guaranteed session cleanup."""
    session = build_session_mock()
    uow = SQLAlchemyUnitOfWork(lambda: session)

    with pytest.raises(asyncio.CancelledError):
        async with uow:
            raise asyncio.CancelledError()

    cast(Any, session.commit).assert_not_awaited()
    cast(Any, session.rollback).assert_awaited_once()
    cast(Any, session.close).assert_awaited_once()
    assert uow.is_active is False


async def test_rollback_failure_on_exception_preserves_original_exception() -> None:
    """Secondary rollback error on exit does not mask the original failure."""
    session = build_session_mock()
    session.rollback = AsyncMock(  # type: ignore[method-assign]
        side_effect=RuntimeError("connection drop during rollback")
    )
    uow = SQLAlchemyUnitOfWork(lambda: session)

    with pytest.raises(ValueError, match="domain validation failed"):
        async with uow:
            raise ValueError("domain validation failed")

    cast(Any, session.close).assert_awaited_once()
    assert uow.is_active is False


async def test_outbox_repository_bound_on_enter() -> None:
    """Unit of Work binds an OutboxRepository to the active session."""
    session = build_session_mock()
    uow = SQLAlchemyUnitOfWork(lambda: session)

    async with uow:
        assert uow.outbox is not None
        assert uow.outbox._session is session


async def test_on_commit_hooks_run_after_successful_commit() -> None:
    """Registered sync and async hooks run in order after session commit succeeds."""
    session = build_session_mock()
    uow = SQLAlchemyUnitOfWork(lambda: session)
    execution_order: list[str] = []

    def sync_hook() -> None:
        execution_order.append("sync_hook")

    async def async_hook() -> None:
        execution_order.append("async_hook")

    async with uow:
        uow.on_commit(sync_hook)
        uow.on_commit(async_hook)
        assert execution_order == []
        await uow.commit()

    assert execution_order == ["sync_hook", "async_hook"]


async def test_on_commit_hooks_not_executed_on_commit_failure() -> None:
    """If session.commit fails, registered post-commit hooks are cleared."""
    session = build_session_mock()
    cast(AsyncMock, session.commit).side_effect = RuntimeError("db commit failure")
    uow = SQLAlchemyUnitOfWork(lambda: session)
    executed = False

    def hook() -> None:
        nonlocal executed
        executed = True

    with pytest.raises(RuntimeError, match="db commit failure"):
        async with uow:
            uow.on_commit(hook)
            await uow.commit()

    assert executed is False


async def test_on_commit_hooks_not_executed_on_rollback_or_exception() -> None:
    """If transaction is rolled back or aborted by exception, hooks do not run."""
    session = build_session_mock()
    uow = SQLAlchemyUnitOfWork(lambda: session)
    executed = False

    def hook() -> None:
        nonlocal executed
        executed = True

    with pytest.raises(ValueError, match="domain error"):
        async with uow:
            uow.on_commit(hook)
            raise ValueError("domain error")

    assert executed is False


async def test_on_commit_hook_exception_logged_without_aborting_other_hooks() -> None:
    """An exception in one hook does not prevent subsequent hooks from running."""
    session = build_session_mock()
    uow = SQLAlchemyUnitOfWork(lambda: session)
    executed: list[str] = []

    def failing_hook() -> None:
        executed.append("failing")
        raise RuntimeError("hook crashed")

    def succeeding_hook() -> None:
        executed.append("succeeding")

    async with uow:
        uow.on_commit(failing_hook)
        uow.on_commit(succeeding_hook)
        await uow.commit()

    assert executed == ["failing", "succeeding"]

