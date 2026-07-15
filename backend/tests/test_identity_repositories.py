"""Tests for identity repositories."""

import uuid
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PaginationParams
from app.modules.identity.models import (
    IdentityPermission,
    IdentityRole,
    IdentityRolePermission,
    IdentityUser,
    IdentityUserRole,
    UserStatus,
)
from app.modules.identity.repository import (
    IdentityPermissionRepository,
    IdentityRoleRepository,
    IdentityUserRepository,
)
from app.modules.identity.schemas import CreateUserRequest, UpdateUserRequest

pytestmark = pytest.mark.asyncio


class ScalarCollection:
    """Simple scalar collection test double."""

    def __init__(self, items: list[Any]) -> None:
        """Initialize with scalar items."""
        self._items = items

    def all(self) -> list[Any]:
        """Return scalar items."""
        return self._items


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


def build_create_user_request(email: str = "OWNER@EXAMPLE.COM") -> CreateUserRequest:
    """Build a valid create user request."""
    return CreateUserRequest(
        email=email,
        first_name="Jane",
        last_name="Doe",
        display_name="Jane Doe",
        password="StrongPassword123!",
    )


async def test_create_user_adds_identity_user() -> None:
    """User repository creates a user from request data."""
    session = build_session_mock()
    repository = IdentityUserRepository(session)

    user = await repository.create_user(build_create_user_request())

    assert isinstance(user, IdentityUser)
    assert user.email == "owner@example.com"
    assert user.status == UserStatus.PENDING
    cast(Any, session.add).assert_called_once_with(user)
    cast(Any, session.flush).assert_awaited_once()


async def test_update_user_mutates_schema_fields() -> None:
    """User repository updates mutable user fields from request data."""
    session = build_session_mock()
    repository = IdentityUserRepository(session)
    user = IdentityUser(
        email="owner@example.com",
        first_name="Jane",
        last_name="Doe",
        display_name="Jane Doe",
        status=UserStatus.PENDING,
        failed_login_attempts=0,
    )

    result = await repository.update_user(
        user,
        UpdateUserRequest(first_name="Janet", status=UserStatus.ACTIVE),
    )

    assert result is user
    assert user.first_name == "Janet"
    assert user.status == UserStatus.ACTIVE
    cast(Any, session.flush).assert_awaited_once()


async def test_exists_by_email_returns_true_for_existing_user() -> None:
    """User repository checks email existence through normalized lookup."""
    session = build_session_mock()
    user = IdentityUser(
        email="owner@example.com",
        first_name="Jane",
        last_name="Doe",
        display_name="Jane Doe",
        status=UserStatus.ACTIVE,
        failed_login_attempts=0,
    )
    cast(Any, session.execute).return_value = ExecuteResult(one_or_none=user)
    repository = IdentityUserRepository(session)

    assert await repository.exists_by_email("OWNER@EXAMPLE.COM") is True


async def test_soft_delete_marks_user_deleted() -> None:
    """User repository soft deletes users."""
    session = build_session_mock()
    repository = IdentityUserRepository(session)
    user = IdentityUser(
        email="owner@example.com",
        first_name="Jane",
        last_name="Doe",
        display_name="Jane Doe",
        status=UserStatus.ACTIVE,
        failed_login_attempts=0,
    )
    user.is_deleted = False
    user.deleted_at = None

    await repository.soft_delete(user)

    assert user.is_deleted is True
    assert user.deleted_at is not None
    cast(Any, session.flush).assert_awaited_once()


async def test_list_users_returns_paginated_result() -> None:
    """User repository returns paginated users."""
    session = build_session_mock()
    user = IdentityUser(
        email="owner@example.com",
        first_name="Jane",
        last_name="Doe",
        display_name="Jane Doe",
        status=UserStatus.ACTIVE,
        failed_login_attempts=0,
    )
    cast(Any, session.execute).return_value = ExecuteResult(items=[user])
    repository = IdentityUserRepository(session)
    cast(Any, repository).count_statement = AsyncMock(return_value=1)

    page = await repository.list_users(PaginationParams(page=1, size=10))

    assert page.items == [user]
    assert page.meta.total == 1
    assert page.meta.page == 1


async def test_lock_and_unlock_user_update_status() -> None:
    """User repository can lock and unlock users."""
    session = build_session_mock()
    repository = IdentityUserRepository(session)
    user = IdentityUser(
        email="owner@example.com",
        first_name="Jane",
        last_name="Doe",
        display_name="Jane Doe",
        status=UserStatus.ACTIVE,
        failed_login_attempts=0,
    )

    await repository.lock_user(user, locked_until=None)
    assert user.status == UserStatus.LOCKED

    await repository.unlock_user(user)
    assert user.status.value == UserStatus.ACTIVE.value
    assert user.locked_until is None


async def test_failed_login_and_last_login_updates() -> None:
    """User repository updates login tracking fields."""
    session = build_session_mock()
    repository = IdentityUserRepository(session)
    user = IdentityUser(
        email="owner@example.com",
        first_name="Jane",
        last_name="Doe",
        display_name="Jane Doe",
        status=UserStatus.ACTIVE,
        failed_login_attempts=0,
    )

    await repository.increment_failed_login(user)
    assert user.failed_login_attempts == 1

    await repository.reset_failed_login(user)
    assert user.failed_login_attempts == 0


async def test_role_assignment_creates_user_role() -> None:
    """Role repository creates user-role assignments."""
    session = build_session_mock()
    repository = IdentityRoleRepository(session)
    user_id = uuid.uuid4()
    role_id = uuid.uuid4()

    assignment = await repository.assign_role(user_id=user_id, role_id=role_id)

    assert isinstance(assignment, IdentityUserRole)
    assert assignment.user_id == user_id
    assert assignment.role_id == role_id
    cast(Any, session.flush).assert_awaited_once()


async def test_role_exists_uses_lookup() -> None:
    """Role repository checks role uniqueness by name."""
    session = build_session_mock()
    cast(Any, session.execute).return_value = ExecuteResult(
        one_or_none=IdentityRole(name="admin", is_system=True)
    )
    repository = IdentityRoleRepository(session)

    assert await repository.role_exists("admin") is True


async def test_permission_assignment_creates_role_permission() -> None:
    """Permission repository creates role-permission assignments."""
    session = build_session_mock()
    repository = IdentityPermissionRepository(session)
    role_id = uuid.uuid4()
    permission_id = uuid.uuid4()

    assignment = await repository.assign_permission(
        role_id=role_id,
        permission_id=permission_id,
    )

    assert isinstance(assignment, IdentityRolePermission)
    assert assignment.role_id == role_id
    assert assignment.permission_id == permission_id
    cast(Any, session.flush).assert_awaited_once()


async def test_list_permissions_returns_assigned_permissions() -> None:
    """Permission repository returns permissions for a role."""
    session = build_session_mock()
    permission = IdentityPermission(name="identity.users.read")
    cast(Any, session.execute).return_value = ExecuteResult(items=[permission])
    repository = IdentityPermissionRepository(session)

    permissions = await repository.list_permissions(uuid.uuid4())

    assert permissions == [permission]
