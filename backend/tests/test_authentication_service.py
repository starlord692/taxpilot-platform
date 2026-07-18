"""Tests for identity authentication service."""

import uuid
from collections.abc import Callable
from typing import cast

import pytest

from app.common.events import EventDispatcher
from app.modules.identity.events import IdentityUserAuthenticatedEvent
from app.modules.identity.exceptions import (
    AuthenticationAccountDisabledException,
    AuthenticationAccountLockedException,
    AuthenticationEmailNotVerifiedException,
    AuthenticationInvalidCredentialsException,
)
from app.modules.identity.models import (
    IdentityCredential,
    IdentityPermission,
    IdentityRole,
    IdentityUser,
    UserStatus,
)
from app.modules.identity.schemas import LoginRequest
from app.modules.identity.services import AuthenticationResult, AuthenticationService
from app.modules.identity.services.authentication_service import (
    AuthenticationUnitOfWork,
)

pytestmark = pytest.mark.asyncio
MAX_FAILED_ATTEMPTS = 3


class StubPasswordVerifier:
    """Deterministic password verifier for authentication tests."""

    def __init__(self, *, valid: bool = True) -> None:
        """Initialize verification behavior."""
        self.valid = valid
        self.seen_hash: str | None = None
        self.seen_password: str | None = None

    def verify(self, hash: str, password: str) -> bool:
        """Return configured verification outcome."""
        self.seen_hash = hash
        self.seen_password = password
        return self.valid


class FakeUserRepository:
    """Fake user repository for authentication tests."""

    def __init__(
        self,
        *,
        user: IdentityUser | None,
        credential: IdentityCredential | None,
    ) -> None:
        """Initialize repository state."""
        self.user = user
        self.credential = credential
        self.incremented = False
        self.reset = False
        self.last_login_updated = False
        self.locked = False

    async def get_by_email(self, email: str) -> IdentityUser | None:
        """Return configured user for matching email."""
        if self.user is not None and self.user.email == email:
            return self.user
        return None

    async def get_credential(self, user_id: uuid.UUID) -> IdentityCredential | None:
        """Return configured credential."""
        if self.credential is not None and self.credential.user_id == user_id:
            return self.credential
        return None

    async def increment_failed_login(self, user: IdentityUser) -> IdentityUser:
        """Increment failed login count."""
        self.incremented = True
        user.failed_login_attempts += 1
        return user

    async def reset_failed_login(self, user: IdentityUser) -> IdentityUser:
        """Reset failed login count."""
        self.reset = True
        user.failed_login_attempts = 0
        return user

    async def lock_user(
        self,
        user: IdentityUser,
        *,
        locked_until: object | None,
    ) -> IdentityUser:
        """Lock the user."""
        self.locked = True
        user.status = UserStatus.LOCKED
        return user

    async def update_last_login(
        self,
        user: IdentityUser,
        *,
        login_at: object,
    ) -> IdentityUser:
        """Update last login."""
        self.last_login_updated = True
        user.last_login_at = login_at  # type: ignore[assignment]
        return user


class FakeRoleRepository:
    """Fake role repository for authentication tests."""

    def __init__(self, roles: list[IdentityRole]) -> None:
        """Initialize role list."""
        self.roles = roles

    async def get_roles(self, user_id: uuid.UUID) -> list[IdentityRole]:
        """Return configured roles."""
        return self.roles


class FakePermissionRepository:
    """Fake permission repository for authentication tests."""

    def __init__(self, permissions: list[IdentityPermission]) -> None:
        """Initialize permission list."""
        self.permissions = permissions
        self.role_ids: list[uuid.UUID] = []

    async def list_permissions_for_roles(
        self,
        role_ids: list[uuid.UUID],
    ) -> list[IdentityPermission]:
        """Return configured permissions."""
        self.role_ids = role_ids
        return self.permissions


class FakeUnitOfWork:
    """Fake authentication Unit of Work."""

    def __init__(
        self,
        *,
        users: FakeUserRepository,
        roles: FakeRoleRepository,
        permissions: FakePermissionRepository,
    ) -> None:
        """Initialize fake repositories."""
        self.users = users
        self.roles = roles
        self.permissions = permissions
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> "FakeUnitOfWork":
        """Enter fake transaction."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Rollback on exceptions or uncommitted work."""
        if exc_type is not None or not self.committed:
            self.rolled_back = True

    async def commit(self) -> None:
        """Mark transaction committed."""
        self.committed = True


def build_user(status: UserStatus = UserStatus.ACTIVE) -> IdentityUser:
    """Build an identity user."""
    user = IdentityUser(
        email="owner@example.com",
        first_name="Jane",
        last_name="Doe",
        display_name="Jane Doe",
        status=status,
        failed_login_attempts=0,
    )
    user.id = uuid.uuid4()
    return user


def build_credential(user_id: uuid.UUID) -> IdentityCredential:
    """Build identity credentials."""
    credential = IdentityCredential(
        user_id=user_id,
        password_hash="$argon2id$hash",
    )
    credential.id = uuid.uuid4()
    return credential


def build_role(name: str) -> IdentityRole:
    """Build an identity role."""
    role = IdentityRole(name=name, is_system=True)
    role.id = uuid.uuid4()
    return role


def build_permission(name: str) -> IdentityPermission:
    """Build an identity permission."""
    permission = IdentityPermission(name=name)
    permission.id = uuid.uuid4()
    return permission


def build_uow(
    *,
    user: IdentityUser | None,
    credential: IdentityCredential | None,
) -> FakeUnitOfWork:
    """Build an authentication Unit of Work fake."""
    return FakeUnitOfWork(
        users=FakeUserRepository(user=user, credential=credential),
        roles=FakeRoleRepository([build_role("member")]),
        permissions=FakePermissionRepository([build_permission("identity.users.read")]),
    )


def build_service(
    uow: FakeUnitOfWork,
    *,
    verifier: StubPasswordVerifier | None = None,
    dispatcher: EventDispatcher | None = None,
) -> AuthenticationService:
    """Build authentication service with fake dependencies."""
    uow_factory = cast(Callable[[], AuthenticationUnitOfWork], lambda: uow)
    return AuthenticationService(
        unit_of_work_factory=uow_factory,
        event_dispatcher=dispatcher or EventDispatcher(),
        password_verifier=verifier or StubPasswordVerifier(),
        max_failed_login_attempts=MAX_FAILED_ATTEMPTS,
    )


def build_request(email: str = "OWNER@EXAMPLE.COM") -> LoginRequest:
    """Build a login request."""
    return LoginRequest(email=email, password="StrongPassword123!")


async def test_successful_authentication() -> None:
    """Authentication returns identity context without tokens."""
    user = build_user()
    uow = build_uow(user=user, credential=build_credential(user.id))
    service = build_service(uow)

    result = await service.authenticate(build_request())

    assert isinstance(result, AuthenticationResult)
    assert result.user_id == user.id
    assert result.email == "owner@example.com"
    assert result.roles == ["member"]
    assert result.permissions == ["identity.users.read"]
    assert uow.users.reset is True
    assert uow.users.last_login_updated is True
    assert uow.committed is True


async def test_invalid_email_raises_invalid_credentials() -> None:
    """Invalid email input raises invalid credentials."""
    user = build_user()
    uow = build_uow(user=user, credential=build_credential(user.id))
    service = build_service(uow)
    request = LoginRequest.model_construct(email="not-an-email", password="secret")

    with pytest.raises(AuthenticationInvalidCredentialsException):
        await service.authenticate(request)

    assert uow.committed is False
    assert uow.rolled_back is False


async def test_wrong_password_increments_failed_login() -> None:
    """Wrong password increments failed login attempts."""
    user = build_user()
    uow = build_uow(user=user, credential=build_credential(user.id))
    service = build_service(uow, verifier=StubPasswordVerifier(valid=False))

    with pytest.raises(AuthenticationInvalidCredentialsException):
        await service.authenticate(build_request())

    assert uow.users.incremented is True
    assert user.failed_login_attempts == 1
    assert uow.committed is False
    assert uow.rolled_back is True


async def test_wrong_password_locks_account_at_limit() -> None:
    """Wrong password locks account when failed attempts reach limit."""
    user = build_user()
    user.failed_login_attempts = MAX_FAILED_ATTEMPTS - 1
    uow = build_uow(user=user, credential=build_credential(user.id))
    service = build_service(uow, verifier=StubPasswordVerifier(valid=False))

    with pytest.raises(AuthenticationInvalidCredentialsException):
        await service.authenticate(build_request())

    assert uow.users.locked is True
    assert user.status == UserStatus.LOCKED


async def test_locked_account_raises_account_locked() -> None:
    """Locked users cannot authenticate."""
    user = build_user(UserStatus.LOCKED)
    uow = build_uow(user=user, credential=build_credential(user.id))
    service = build_service(uow)

    with pytest.raises(AuthenticationAccountLockedException):
        await service.authenticate(build_request())


async def test_disabled_account_raises_account_disabled() -> None:
    """Disabled users cannot authenticate."""
    user = build_user(UserStatus.DISABLED)
    uow = build_uow(user=user, credential=build_credential(user.id))
    service = build_service(uow)

    with pytest.raises(AuthenticationAccountDisabledException):
        await service.authenticate(build_request())


async def test_pending_account_raises_email_not_verified() -> None:
    """Pending users cannot authenticate."""
    user = build_user(UserStatus.PENDING)
    uow = build_uow(user=user, credential=build_credential(user.id))
    service = build_service(uow)

    with pytest.raises(AuthenticationEmailNotVerifiedException):
        await service.authenticate(build_request())


async def test_failed_login_reset_on_success() -> None:
    """Successful authentication resets failed login attempts."""
    user = build_user()
    user.failed_login_attempts = 2
    uow = build_uow(user=user, credential=build_credential(user.id))
    service = build_service(uow)

    await service.authenticate(build_request())

    assert uow.users.reset is True
    assert user.failed_login_attempts == 0


async def test_event_published() -> None:
    """Successful authentication publishes user-authenticated event."""
    user = build_user()
    uow = build_uow(user=user, credential=build_credential(user.id))
    dispatcher = EventDispatcher()
    published_events: list[IdentityUserAuthenticatedEvent] = []

    def handle_authenticated(event: IdentityUserAuthenticatedEvent) -> None:
        published_events.append(event)

    dispatcher.register(IdentityUserAuthenticatedEvent, handle_authenticated)
    service = build_service(uow, dispatcher=dispatcher)

    await service.authenticate(build_request())

    assert len(published_events) == 1
    assert published_events[0].event_name == "identity.user_authenticated"
    assert published_events[0].user_id == user.id
