"""Tests for identity registration service."""

import uuid
from collections.abc import Callable
from typing import cast

import pytest

from app.common.events import EventDispatcher
from app.common.exceptions import ConflictException
from app.modules.identity.events import IdentityUserCreatedEvent
from app.modules.identity.exceptions import IdentityEmailAlreadyExistsException
from app.modules.identity.models import (
    IdentityCredential,
    IdentityRole,
    IdentityUser,
    IdentityUserRole,
    UserStatus,
)
from app.modules.identity.schemas import CreateUserRequest
from app.modules.identity.services import RegistrationService
from app.modules.identity.services.registration_service import RegistrationUnitOfWork

pytestmark = pytest.mark.asyncio


class StubPasswordHasher:
    """Deterministic password hasher for registration tests."""

    def __init__(self) -> None:
        """Initialize captured values."""
        self.raw_password: str | None = None

    def hash(self, password: str) -> str:
        """Return a deterministic non-raw password hash."""
        self.raw_password = password
        return "$argon2id$hashed-password"


class FakeUserRepository:
    """Fake user repository for registration tests."""

    def __init__(self, *, email_exists: bool = False) -> None:
        """Initialize fake repository state."""
        self.email_exists = email_exists
        self.created_user: IdentityUser | None = None
        self.created_credential: IdentityCredential | None = None

    async def exists_by_email(self, email: str) -> bool:
        """Return configured email existence."""
        return self.email_exists

    async def create_user(self, request: CreateUserRequest) -> IdentityUser:
        """Create an in-memory identity user."""
        user = IdentityUser(
            email=request.email,
            first_name=request.first_name,
            last_name=request.last_name,
            display_name=request.display_name or "Jane Doe",
            status=UserStatus.PENDING,
            failed_login_attempts=0,
        )
        user.id = uuid.uuid4()
        self.created_user = user
        return user

    async def create_credential(
        self,
        *,
        user_id: uuid.UUID,
        password_hash: str,
    ) -> IdentityCredential:
        """Create an in-memory credential."""
        credential = IdentityCredential(
            user_id=user_id,
            password_hash=password_hash,
        )
        credential.id = uuid.uuid4()
        self.created_credential = credential
        return credential


class FakeRoleRepository:
    """Fake role repository for registration tests."""

    def __init__(
        self,
        *,
        member_role: IdentityRole | None = None,
        fail_assignment: bool = False,
    ) -> None:
        """Initialize fake role repository state."""
        self.member_role = member_role
        self.fail_assignment = fail_assignment
        self.assigned_role: IdentityUserRole | None = None

    async def get_by_name(self, name: str) -> IdentityRole | None:
        """Return the configured role."""
        return self.member_role if name == "member" else None

    async def create_role(
        self,
        *,
        name: str,
        description: str | None = None,
        is_system: bool = False,
    ) -> IdentityRole:
        """Create an in-memory role."""
        role = IdentityRole(
            name=name,
            description=description,
            is_system=is_system,
        )
        role.id = uuid.uuid4()
        self.member_role = role
        return role

    async def assign_role(
        self,
        *,
        user_id: uuid.UUID,
        role_id: uuid.UUID,
        assigned_by: uuid.UUID | None = None,
    ) -> IdentityUserRole:
        """Assign a role to a user."""
        if self.fail_assignment:
            raise ConflictException("Role assignment failed")
        assignment = IdentityUserRole(
            user_id=user_id,
            role_id=role_id,
            assigned_by=assigned_by,
        )
        assignment.id = uuid.uuid4()
        self.assigned_role = assignment
        return assignment


class FakeUnitOfWork:
    """Fake Unit of Work for registration tests."""

    def __init__(
        self,
        *,
        users: FakeUserRepository | None = None,
        roles: FakeRoleRepository | None = None,
    ) -> None:
        """Initialize fake Unit of Work state."""
        self.users = users or FakeUserRepository()
        self.roles = roles or FakeRoleRepository()
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> "FakeUnitOfWork":
        """Enter fake transaction scope."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Rollback when an exception occurs or commit did not happen."""
        if exc_type is not None or not self.committed:
            await self.rollback()

    async def commit(self) -> None:
        """Mark the transaction committed."""
        self.committed = True

    async def rollback(self) -> None:
        """Mark the transaction rolled back."""
        self.rolled_back = True


def build_request(password: str = "StrongPassword123!") -> CreateUserRequest:
    """Build a valid create user request."""
    return CreateUserRequest(
        email="OWNER@EXAMPLE.COM",
        first_name="Jane",
        last_name="Doe",
        display_name="Jane Doe",
        password=password,
    )


def build_service(
    uow: FakeUnitOfWork,
    dispatcher: EventDispatcher | None = None,
    hasher: StubPasswordHasher | None = None,
) -> RegistrationService:
    """Build a registration service with fake dependencies."""
    uow_factory = cast(Callable[[], RegistrationUnitOfWork], lambda: uow)
    return RegistrationService(
        unit_of_work_factory=uow_factory,
        event_dispatcher=dispatcher or EventDispatcher(),
        password_hasher=hasher or StubPasswordHasher(),
    )


async def test_successful_registration() -> None:
    """Registration creates a pending user and returns a response schema."""
    uow = FakeUnitOfWork()
    service = build_service(uow)

    response = await service.register_user(build_request())

    assert response.email == "owner@example.com"
    assert response.status == UserStatus.PENDING
    assert uow.committed is True
    assert uow.rolled_back is False


async def test_duplicate_email_raises_identity_error() -> None:
    """Duplicate email raises identity.email_already_exists."""
    uow = FakeUnitOfWork(users=FakeUserRepository(email_exists=True))
    service = build_service(uow)

    with pytest.raises(IdentityEmailAlreadyExistsException) as exc_info:
        await service.register_user(build_request())

    assert exc_info.value.error_code == "identity.email_already_exists"
    assert uow.committed is False
    assert uow.rolled_back is True


async def test_weak_password_is_rejected() -> None:
    """Weak passwords are rejected even when schema validation was bypassed."""
    request = CreateUserRequest.model_construct(
        email="owner@example.com",
        first_name="Jane",
        last_name="Doe",
        display_name="Jane Doe",
        password="weak",
    )
    uow = FakeUnitOfWork()
    service = build_service(uow)

    with pytest.raises(ValueError):
        await service.register_user(request)

    assert uow.committed is False
    assert uow.rolled_back is False


async def test_transaction_rollback_when_assignment_fails() -> None:
    """Registration rolls back when a later repository operation fails."""
    uow = FakeUnitOfWork(roles=FakeRoleRepository(fail_assignment=True))
    service = build_service(uow)

    with pytest.raises(ConflictException):
        await service.register_user(build_request())

    assert uow.committed is False
    assert uow.rolled_back is True


async def test_default_role_assigned() -> None:
    """Registration assigns the default member role."""
    uow = FakeUnitOfWork()
    service = build_service(uow)

    await service.register_user(build_request())

    assert uow.roles.member_role is not None
    assert uow.roles.member_role.name == "member"
    assert uow.roles.assigned_role is not None
    assert uow.users.created_user is not None
    assert uow.roles.assigned_role.user_id == uow.users.created_user.id


async def test_password_is_hashed() -> None:
    """Registration stores a hash and never stores the raw password."""
    uow = FakeUnitOfWork()
    hasher = StubPasswordHasher()
    service = build_service(uow, hasher=hasher)

    await service.register_user(build_request())

    assert hasher.raw_password == "StrongPassword123!"
    assert uow.users.created_credential is not None
    assert uow.users.created_credential.password_hash == "$argon2id$hashed-password"
    assert uow.users.created_credential.password_hash != "StrongPassword123!"


async def test_event_published() -> None:
    """Registration publishes identity.user_created."""
    uow = FakeUnitOfWork()
    dispatcher = EventDispatcher()
    published_events: list[IdentityUserCreatedEvent] = []

    def handle_user_created(event: IdentityUserCreatedEvent) -> None:
        published_events.append(event)

    dispatcher.register(IdentityUserCreatedEvent, handle_user_created)
    service = build_service(uow, dispatcher=dispatcher)

    await service.register_user(build_request())

    assert len(published_events) == 1
    assert published_events[0].event_name == "identity.user_created"
    assert published_events[0].email == "owner@example.com"
