"""Identity registration service."""

import uuid
from collections.abc import Callable
from typing import Protocol

from argon2 import PasswordHasher
from argon2.low_level import Type

from app.common.events import EventDispatcher
from app.modules.identity.events import IdentityUserCreatedEvent
from app.modules.identity.exceptions import IdentityEmailAlreadyExistsException
from app.modules.identity.models import (
    IdentityCredential,
    IdentityRole,
    IdentityUser,
    IdentityUserRole,
)
from app.modules.identity.schemas import CreateUserRequest, UserResponse
from app.modules.identity.validators import (
    normalize_and_validate_email,
    validate_password_strength,
)

DEFAULT_ROLE_NAME = "member"


class PasswordHasherProtocol(Protocol):
    """Password hasher dependency contract."""

    def hash(self, password: str) -> str:
        """Hash a plain password."""


class UserRegistrationRepository(Protocol):
    """User repository behavior required by registration."""

    async def exists_by_email(self, email: str) -> bool:
        """Return whether a user exists by email."""
        ...

    async def create_user(self, request: CreateUserRequest) -> IdentityUser:
        """Create an identity user."""
        ...

    async def create_credential(
        self,
        *,
        user_id: uuid.UUID,
        password_hash: str,
    ) -> IdentityCredential:
        """Create user credentials."""
        ...


class RoleRegistrationRepository(Protocol):
    """Role repository behavior required by registration."""

    async def get_by_name(self, name: str) -> IdentityRole | None:
        """Return a role by name."""
        ...

    async def create_role(
        self,
        *,
        name: str,
        description: str | None = None,
        is_system: bool = False,
    ) -> IdentityRole:
        """Create a role."""
        ...

    async def assign_role(
        self,
        *,
        user_id: uuid.UUID,
        role_id: uuid.UUID,
        assigned_by: uuid.UUID | None = None,
    ) -> IdentityUserRole:
        """Assign a role."""
        ...


class RegistrationUnitOfWork(Protocol):
    """Unit of Work contract required by registration."""

    users: UserRegistrationRepository
    roles: RoleRegistrationRepository

    async def __aenter__(self) -> "RegistrationUnitOfWork":
        """Enter the registration transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the registration transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit the registration transaction."""
        ...


UnitOfWorkFactory = Callable[[], RegistrationUnitOfWork]


class RegistrationService:
    """Register new identity users."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
        password_hasher: PasswordHasherProtocol | None = None,
    ) -> None:
        """Initialize the service with injected dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher
        self._password_hasher = password_hasher or PasswordHasher(type=Type.ID)

    async def register_user(self, request: CreateUserRequest) -> UserResponse:
        """Register a new pending identity user."""
        validated_request = CreateUserRequest.model_validate(request)
        email = normalize_and_validate_email(validated_request.email)
        validate_password_strength(validated_request.password)

        async with self._unit_of_work_factory() as uow:
            if await uow.users.exists_by_email(email):
                raise IdentityEmailAlreadyExistsException(
                    "Email already exists",
                    details={"email": email},
                )

            user = await uow.users.create_user(
                validated_request.model_copy(update={"email": email})
            )
            password_hash = self._password_hasher.hash(validated_request.password)
            await uow.users.create_credential(
                user_id=user.id,
                password_hash=password_hash,
            )

            member_role = await self._get_or_create_member_role(uow)
            await uow.roles.assign_role(user_id=user.id, role_id=member_role.id)

            await self._event_dispatcher.dispatch(
                IdentityUserCreatedEvent(user_id=user.id, email=user.email)
            )
            await uow.commit()

        return UserResponse.model_validate(user)

    async def _get_or_create_member_role(
        self,
        uow: RegistrationUnitOfWork,
    ) -> IdentityRole:
        """Return the default member role, creating it when absent."""
        member_role = await uow.roles.get_by_name(DEFAULT_ROLE_NAME)
        if member_role is not None:
            return member_role
        return await uow.roles.create_role(
            name=DEFAULT_ROLE_NAME,
            description="Default member role",
            is_system=True,
        )
