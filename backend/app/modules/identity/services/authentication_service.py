"""Identity authentication service."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type

from app.common.events import EventDispatcher
from app.common.models.abstract.timestamp import utc_now
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
from app.modules.identity.validators import normalize_and_validate_email

DEFAULT_MAX_FAILED_LOGIN_ATTEMPTS = 5


@dataclass(frozen=True)
class AuthenticationResult:
    """Result returned after successful credential authentication."""

    user_id: uuid.UUID
    email: str
    roles: list[str]
    permissions: list[str]


class PasswordVerifierProtocol(Protocol):
    """Password verifier dependency contract."""

    def verify(self, hash: str, password: str) -> bool:
        """Verify a plain password against a hash."""
        ...


class AuthenticationUserRepository(Protocol):
    """User repository behavior required by authentication."""

    async def get_by_email(self, email: str) -> IdentityUser | None:
        """Return a user by email."""
        ...

    async def get_credential(self, user_id: uuid.UUID) -> IdentityCredential | None:
        """Return credentials for a user."""
        ...

    async def increment_failed_login(self, user: IdentityUser) -> IdentityUser:
        """Increment failed login count."""
        ...

    async def reset_failed_login(self, user: IdentityUser) -> IdentityUser:
        """Reset failed login count."""
        ...

    async def lock_user(
        self,
        user: IdentityUser,
        *,
        locked_until: object | None,
    ) -> IdentityUser:
        """Lock a user."""
        ...

    async def update_last_login(
        self,
        user: IdentityUser,
        *,
        login_at: object,
    ) -> IdentityUser:
        """Update last login timestamp."""
        ...


class AuthenticationRoleRepository(Protocol):
    """Role repository behavior required by authentication."""

    async def get_roles(self, user_id: uuid.UUID) -> list[IdentityRole]:
        """Return roles assigned to a user."""
        ...


class AuthenticationPermissionRepository(Protocol):
    """Permission repository behavior required by authentication."""

    async def list_permissions_for_roles(
        self,
        role_ids: list[uuid.UUID],
    ) -> list[IdentityPermission]:
        """Return permissions for roles."""
        ...


class AuthenticationUnitOfWork(Protocol):
    """Unit of Work contract required by authentication."""

    users: AuthenticationUserRepository
    roles: AuthenticationRoleRepository
    permissions: AuthenticationPermissionRepository

    async def __aenter__(self) -> "AuthenticationUnitOfWork":
        """Enter the authentication transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the authentication transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit the authentication transaction."""
        ...


UnitOfWorkFactory = Callable[[], AuthenticationUnitOfWork]


class AuthenticationService:
    """Authenticate identity users with email and password."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
        password_verifier: PasswordVerifierProtocol | None = None,
        max_failed_login_attempts: int = DEFAULT_MAX_FAILED_LOGIN_ATTEMPTS,
    ) -> None:
        """Initialize the service with injected dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher
        self._password_verifier = password_verifier or PasswordHasher(type=Type.ID)
        self._max_failed_login_attempts = max_failed_login_attempts

    async def authenticate(self, request: LoginRequest) -> AuthenticationResult:
        """Authenticate a user and return identity authorization context."""
        email = self._normalize_email(request.email)

        async with self._unit_of_work_factory() as uow:
            user = await uow.users.get_by_email(email)
            if user is None:
                raise AuthenticationInvalidCredentialsException("Invalid credentials")

            credential = await uow.users.get_credential(user.id)
            if credential is None or not self._verify_password(
                credential.password_hash,
                request.password,
            ):
                await self._handle_failed_login(uow, user)
                raise AuthenticationInvalidCredentialsException("Invalid credentials")

            self._ensure_authenticatable(user)

            await uow.users.reset_failed_login(user)
            await uow.users.update_last_login(user, login_at=utc_now())

            roles = await uow.roles.get_roles(user.id)
            permissions = await uow.permissions.list_permissions_for_roles(
                [role.id for role in roles]
            )

            await self._event_dispatcher.dispatch(
                IdentityUserAuthenticatedEvent(user_id=user.id, email=user.email)
            )
            await uow.commit()

        return AuthenticationResult(
            user_id=user.id,
            email=user.email,
            roles=[role.name for role in roles],
            permissions=[permission.name for permission in permissions],
        )

    def _normalize_email(self, email: str) -> str:
        """Normalize email or raise invalid credentials."""
        try:
            return normalize_and_validate_email(email)
        except ValueError as exc:
            raise AuthenticationInvalidCredentialsException(
                "Invalid credentials"
            ) from exc

    def _verify_password(self, password_hash: str, password: str) -> bool:
        """Verify a password with Argon2id."""
        try:
            return self._password_verifier.verify(password_hash, password)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False

    async def _handle_failed_login(
        self,
        uow: AuthenticationUnitOfWork,
        user: IdentityUser,
    ) -> None:
        """Increment failures and lock account when limit is reached."""
        await uow.users.increment_failed_login(user)
        if user.failed_login_attempts >= self._max_failed_login_attempts:
            await uow.users.lock_user(user, locked_until=None)

    def _ensure_authenticatable(self, user: IdentityUser) -> None:
        """Raise status-specific authentication errors."""
        if user.status == UserStatus.PENDING:
            raise AuthenticationEmailNotVerifiedException("Email is not verified")
        if user.status == UserStatus.LOCKED:
            raise AuthenticationAccountLockedException("Account is locked")
        if user.status == UserStatus.DISABLED:
            raise AuthenticationAccountDisabledException("Account is disabled")
