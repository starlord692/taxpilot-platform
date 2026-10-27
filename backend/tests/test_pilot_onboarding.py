"""Unit tests for administrative pilot onboarding command and service."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from argon2 import PasswordHasher
from argon2.low_level import Type

from app.core.config import Settings
from app.modules.accounting.chart_of_accounts.models import Account
from app.modules.business.models import (
    Business,
    BusinessMembership,
    BusinessType,
)
from app.modules.business.schemas import CreateBusinessRequest
from app.modules.identity.models import (
    IdentityCredential,
    IdentityRole,
    IdentityUser,
    UserStatus,
)
from app.modules.identity.schemas import CreateUserRequest, UpdateUserRequest
from scripts.seed_pilot_business import (
    DEFAULT_DATABASE_URL,
    OWNER_ROLE,
    PilotOnboardingConfig,
    PilotOnboardingConflictException,
    PilotOnboardingEnvironmentError,
    PilotOnboardingService,
    PilotOnboardingValidationError,
    build_argument_parser,
    main,
)

VALID_PASSWORD = "StrongP@ssw0rd2026!"
DEFAULT_COA_COUNT = 33


class FakeUserRepository:
    """In-memory user repository for onboarding tests."""

    def __init__(self) -> None:
        self.users: dict[str, IdentityUser] = {}
        self.credentials: dict[uuid.UUID, IdentityCredential] = {}

    async def get_by_email(self, email: str) -> IdentityUser | None:
        return self.users.get(email.lower())

    async def create_user(self, request: CreateUserRequest) -> IdentityUser:
        user_id = uuid.uuid4()
        user = IdentityUser(
            id=user_id,
            email=request.email.lower(),
            first_name=request.first_name,
            last_name=request.last_name,
            display_name=request.display_name,
            status=UserStatus.PENDING,
        )
        self.users[request.email.lower()] = user
        return user

    async def create_credential(
        self,
        *,
        user_id: uuid.UUID,
        password_hash: str,
    ) -> IdentityCredential:
        cred = IdentityCredential(
            id=uuid.uuid4(),
            user_id=user_id,
            password_hash=password_hash,
        )
        self.credentials[user_id] = cred
        return cred

    async def get_credential(self, user_id: uuid.UUID) -> IdentityCredential | None:
        return self.credentials.get(user_id)

    async def update_user(
        self,
        user: IdentityUser,
        request: UpdateUserRequest,
    ) -> IdentityUser:
        if request.status is not None:
            user.status = request.status
        if request.first_name is not None:
            user.first_name = request.first_name
        if request.last_name is not None:
            user.last_name = request.last_name
        if request.display_name is not None:
            user.display_name = request.display_name
        self.users[user.email] = user
        return user


class FakeRoleRepository:
    """In-memory role repository for onboarding tests."""

    def __init__(self) -> None:
        self.roles: dict[str, IdentityRole] = {}
        self.user_roles: dict[uuid.UUID, list[uuid.UUID]] = {}

    async def get_by_name(self, name: str) -> IdentityRole | None:
        return self.roles.get(name)

    async def create_role(
        self,
        *,
        name: str,
        description: str | None = None,
        is_system: bool = False,
    ) -> IdentityRole:
        role = IdentityRole(
            id=uuid.uuid4(),
            name=name,
            description=description,
            is_system=is_system,
        )
        self.roles[name] = role
        return role

    async def assign_role(
        self,
        *,
        user_id: uuid.UUID,
        role_id: uuid.UUID,
        assigned_by: uuid.UUID | None = None,
    ) -> None:
        self.user_roles.setdefault(user_id, []).append(role_id)


class FakeBusinessRepository:
    """In-memory business repository for onboarding tests."""

    def __init__(self) -> None:
        self.businesses: dict[str, Business] = {}

    async def get_by_legal_name(self, legal_name: str) -> Business | None:
        return self.businesses.get(legal_name.lower())

    async def create_business(
        self,
        request: CreateBusinessRequest,
        *,
        business_code: str | None = None,
    ) -> Business:
        biz_id = uuid.uuid4()
        business = Business(
            id=biz_id,
            business_code=business_code,
            legal_name=request.legal_name,
            trade_name=request.trade_name,
            business_type=request.business_type,
            registration_status=request.registration_status,
            business_email=request.business_email,
            business_phone=request.business_phone,
            status="active",
        )
        self.businesses[request.legal_name.lower()] = business
        return business


class FakeBusinessMembershipRepository:
    """In-memory business membership repository for onboarding tests."""

    def __init__(self) -> None:
        self.memberships: list[BusinessMembership] = []

    async def add_member(
        self,
        *,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str,
    ) -> BusinessMembership:
        membership = BusinessMembership(
            id=uuid.uuid4(),
            business_id=business_id,
            user_id=user_id,
            role=role,
        )
        self.memberships.append(membership)
        return membership

    async def get_members(self, business_id: uuid.UUID) -> list[BusinessMembership]:
        return [m for m in self.memberships if m.business_id == business_id]

    async def get_membership(
        self,
        *,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> BusinessMembership | None:
        for m in self.memberships:
            if m.business_id == business_id and m.user_id == user_id:
                return m
        return None


class FakeChartOfAccountsRepository:
    """In-memory chart of accounts repository for onboarding tests."""

    def __init__(self) -> None:
        self.accounts: list[Account] = []

    async def list_accounts(
        self,
        *,
        business_id: uuid.UUID,
        category: str | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> list[Account]:
        return [a for a in self.accounts if a.business_id == business_id]

    async def create_account(
        self,
        *,
        business_id: uuid.UUID,
        account_code: str,
        account_name: str,
        account_type_id: uuid.UUID,
        is_system: bool,
    ) -> Account:
        account = Account(
            id=uuid.uuid4(),
            business_id=business_id,
            account_code=account_code,
            account_name=account_name,
            account_type_id=account_type_id,
            is_system=is_system,
            is_active=True,
        )
        self.accounts.append(account)
        return account


class FakeChartInitializer:
    """Fake chart initializer recording calls."""

    def __init__(self, account_count: int = 33) -> None:
        self.account_count = account_count
        self.call_count = 0

    async def initialize_default_chart(
        self,
        business_id: uuid.UUID,
        uow: Any,
    ) -> list[Account]:
        self.call_count += 1
        created: list[Account] = []
        core_codes = ["1000", "1010", "1020", "1030", "2000", "2010", "3000", "4000"]
        for i in range(self.account_count):
            code = core_codes[i] if i < len(core_codes) else f"{5000 + i}"
            account = await uow.chart_of_accounts.create_account(
                business_id=business_id,
                account_code=code,
                account_name=f"Account {code}",
                account_type_id=uuid.uuid4(),
                is_system=True,
            )
            created.append(account)
        return created


class FakeOnboardingUnitOfWork:
    """Fake Unit of Work coordinating repositories for onboarding tests."""

    def __init__(
        self,
        users: FakeUserRepository,
        roles: FakeRoleRepository,
        businesses: FakeBusinessRepository,
        memberships: FakeBusinessMembershipRepository,
        chart: FakeChartOfAccountsRepository,
    ) -> None:
        self.users = users
        self.roles = roles
        self.businesses = businesses
        self.business_memberships = memberships
        self.chart_of_accounts = chart
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> FakeOnboardingUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        if exc_type is not None or not self.committed:
            self.rolled_back = True

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True
        self.committed = False


@pytest.fixture
def test_env_harness() -> tuple[
    FakeUserRepository,
    FakeRoleRepository,
    FakeBusinessRepository,
    FakeBusinessMembershipRepository,
    FakeChartOfAccountsRepository,
    FakeChartInitializer,
    FakeOnboardingUnitOfWork,
    PilotOnboardingService,
]:
    """Provide a fresh in-memory onboarding test harness."""
    users = FakeUserRepository()
    roles = FakeRoleRepository()
    businesses = FakeBusinessRepository()
    memberships = FakeBusinessMembershipRepository()
    chart = FakeChartOfAccountsRepository()
    initializer = FakeChartInitializer(account_count=33)

    uow = FakeOnboardingUnitOfWork(
        users=users,
        roles=roles,
        businesses=businesses,
        memberships=memberships,
        chart=chart,
    )

    settings = Settings(
        environment="staging",
        identity_token_secret_key="a" * 32,
        database_url="postgresql+asyncpg://taxpilot:taxpilot@staging-db.internal:5432/taxpilot_staging",
    )

    service = PilotOnboardingService(
        unit_of_work_factory=lambda: uow,
        chart_initializer=initializer,
        settings=settings,
    )
    return (
        users,
        roles,
        businesses,
        memberships,
        chart,
        initializer,
        uow,
        service,
    )


@pytest.mark.asyncio
async def test_first_time_onboarding_orchestration(
    test_env_harness: Any,
) -> None:
    """First-time onboarding creates user, credentials, biz, membership, CoA."""
    (
        users,
        roles,
        businesses,
        memberships,
        chart,
        initializer,
        uow,
        service,
    ) = test_env_harness

    config = PilotOnboardingConfig(
        environment="staging",
        owner_email="pilot.owner@example.com",
        owner_first_name="Priya",
        owner_last_name="Sharma",
        business_legal_name="Apex Logistics Private Limited",
        business_trade_name="Apex Logistics",
        business_type=BusinessType.PRIVATE_LIMITED,
        activate_owner=True,
        password=VALID_PASSWORD,
    )

    result = await service.execute(config)

    assert result.success is True
    assert result.user_created is True
    assert result.user_activated is True
    assert result.user_status == "active"
    assert result.business_created is True
    assert result.membership_created is True
    assert result.membership_role == OWNER_ROLE
    assert result.accounts_initialized == DEFAULT_COA_COUNT
    assert result.accounts_already_present == 0
    assert result.dry_run is False
    assert uow.committed is True

    # Verify user state
    stored_user = users.users.get("pilot.owner@example.com")
    assert stored_user is not None
    assert stored_user.status == UserStatus.ACTIVE

    # Verify credential stored as Argon2id hash, not plaintext
    cred = users.credentials.get(stored_user.id)
    assert cred is not None
    assert cred.password_hash.startswith("$argon2id$")
    assert VALID_PASSWORD not in cred.password_hash

    # Verify role assigned
    assert "member" in roles.roles
    assert roles.user_roles[stored_user.id] == [roles.roles["member"].id]

    # Verify business state
    stored_biz = businesses.businesses.get("apex logistics private limited")
    assert stored_biz is not None
    assert stored_biz.legal_name == "Apex Logistics Private Limited"

    # Verify membership
    biz_members = memberships.memberships
    assert len(biz_members) == 1
    assert biz_members[0].business_id == stored_biz.id
    assert biz_members[0].user_id == stored_user.id
    assert biz_members[0].role == OWNER_ROLE

    # Verify Chart of Accounts
    assert initializer.call_count == 1
    assert len(chart.accounts) == DEFAULT_COA_COUNT


@pytest.mark.asyncio
async def test_idempotent_repeat_execution(
    test_env_harness: Any,
) -> None:
    """Repeated execution does not duplicate user, business, membership, or accounts."""
    (
        users,
        roles,
        businesses,
        memberships,
        chart,
        initializer,
        uow,
        service,
    ) = test_env_harness

    config = PilotOnboardingConfig(
        environment="staging",
        owner_email="pilot.owner@example.com",
        owner_first_name="Priya",
        owner_last_name="Sharma",
        business_legal_name="Apex Logistics Private Limited",
        activate_owner=True,
        password=VALID_PASSWORD,
    )

    result1 = await service.execute(config)
    assert result1.success is True
    assert result1.user_created is True
    assert result1.business_created is True

    # Reset commit tracker for second run
    uow.committed = False

    result2 = await service.execute(config)
    assert result2.success is True
    assert result2.user_created is False
    assert result2.business_created is False
    assert result2.membership_created is False
    assert result2.accounts_initialized == 0
    assert result2.accounts_already_present == DEFAULT_COA_COUNT
    assert uow.committed is True

    # Assert no duplicate entries created
    assert len(users.users) == 1
    assert len(businesses.businesses) == 1
    assert len(memberships.memberships) == 1
    assert len(chart.accounts) == DEFAULT_COA_COUNT
    assert initializer.call_count == 1  # Not called on repeat run


@pytest.mark.asyncio
async def test_pending_status_when_activate_is_false(
    test_env_harness: Any,
) -> None:
    """When activate_owner is False, newly created user remains PENDING."""
    (
        users,
        _,
        _,
        _,
        _,
        _,
        _,
        service,
    ) = test_env_harness

    config = PilotOnboardingConfig(
        environment="staging",
        owner_email="pending.owner@example.com",
        owner_first_name="Raj",
        owner_last_name="Patel",
        business_legal_name="Patel Enterprises LLP",
        activate_owner=False,
        password=VALID_PASSWORD,
    )

    result = await service.execute(config)
    assert result.user_created is True
    assert result.user_activated is False
    assert result.user_status == "pending"

    stored_user = users.users.get("pending.owner@example.com")
    assert stored_user is not None
    assert stored_user.status == UserStatus.PENDING


@pytest.mark.asyncio
async def test_conflicting_business_ownership_raises_conflict(
    test_env_harness: Any,
) -> None:
    """Fails safely without altering ownership when biz belongs to another."""
    (
        users,
        _,
        businesses,
        memberships,
        _,
        _,
        uow,
        service,
    ) = test_env_harness

    # Pre-existing business and original owner
    original_owner_id = uuid.uuid4()
    original_biz = Business(
        id=uuid.uuid4(),
        legal_name="Shared Business Private Limited",
        trade_name=None,
        business_type=BusinessType.PRIVATE_LIMITED,
        registration_status="registered",
        status="active",
    )
    businesses.businesses["shared business private limited"] = original_biz
    memberships.memberships.append(
        BusinessMembership(
            id=uuid.uuid4(),
            business_id=original_biz.id,
            user_id=original_owner_id,
            role=OWNER_ROLE,
        )
    )

    # Attempt to onboard a different user for the same business
    config = PilotOnboardingConfig(
        environment="staging",
        owner_email="intruder@example.com",
        owner_first_name="Intruder",
        owner_last_name="User",
        business_legal_name="Shared Business Private Limited",
        activate_owner=True,
        password=VALID_PASSWORD,
    )

    with pytest.raises(PilotOnboardingConflictException) as exc_info:
        await service.execute(config)

    assert "owned by a different user" in str(exc_info.value)
    assert uow.committed is False


@pytest.mark.asyncio
async def test_conflicting_non_owner_role_raises_conflict(
    test_env_harness: Any,
) -> None:
    """Fails safely when user already has non-owner role in the business."""
    (
        users,
        _,
        businesses,
        memberships,
        _,
        _,
        uow,
        service,
    ) = test_env_harness

    existing_user_id = uuid.uuid4()
    existing_user = IdentityUser(
        id=existing_user_id,
        email="staff@example.com",
        first_name="Staff",
        last_name="Member",
        status=UserStatus.ACTIVE,
    )
    users.users["staff@example.com"] = existing_user

    existing_biz = Business(
        id=uuid.uuid4(),
        legal_name="Existing Co",
        business_type=BusinessType.PRIVATE_LIMITED,
        status="active",
    )
    businesses.businesses["existing co"] = existing_biz
    memberships.memberships.append(
        BusinessMembership(
            id=uuid.uuid4(),
            business_id=existing_biz.id,
            user_id=existing_user_id,
            role="accountant",
        )
    )

    config = PilotOnboardingConfig(
        environment="staging",
        owner_email="staff@example.com",
        owner_first_name="Staff",
        owner_last_name="Member",
        business_legal_name="Existing Co",
        activate_owner=True,
    )

    with pytest.raises(PilotOnboardingConflictException) as exc_info:
        await service.execute(config)

    assert "non-owner role 'accountant'" in str(exc_info.value)
    assert uow.committed is False


@pytest.mark.asyncio
async def test_production_environment_is_strictly_refused(
    test_env_harness: Any,
) -> None:
    """Execution against production environment is refused immediately."""
    *_, service = test_env_harness

    config = PilotOnboardingConfig(
        environment="production",
        owner_email="owner@prod.com",
        owner_first_name="Prod",
        owner_last_name="Owner",
        business_legal_name="Prod Corp",
        password=VALID_PASSWORD,
    )

    with pytest.raises(PilotOnboardingEnvironmentError) as exc_info:
        await service.execute(config)

    assert "strictly prohibited in 'production'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_missing_environment_fails_closed(
    test_env_harness: Any,
) -> None:
    """Missing or empty environment configuration fails closed."""
    *_, service = test_env_harness

    config = PilotOnboardingConfig(
        environment="",
        owner_email="owner@test.com",
        owner_first_name="Test",
        owner_last_name="Owner",
        business_legal_name="Test Corp",
        password=VALID_PASSWORD,
    )

    with pytest.raises(PilotOnboardingEnvironmentError) as exc_info:
        await service.execute(config)

    assert "Target environment must be explicitly provided" in str(exc_info.value)


@pytest.mark.asyncio
async def test_dry_run_does_not_commit(
    test_env_harness: Any,
) -> None:
    """Dry-run completes orchestration but does not commit changes."""
    *_, uow, service = test_env_harness

    config = PilotOnboardingConfig(
        environment="staging",
        owner_email="dryrun@example.com",
        owner_first_name="Dry",
        owner_last_name="Run",
        business_legal_name="Dry Run Logistics",
        activate_owner=True,
        dry_run=True,
        password=VALID_PASSWORD,
    )

    result = await service.execute(config)

    assert result.success is True
    assert result.dry_run is True
    assert uow.committed is False
    assert uow.rolled_back is True
    assert any("Dry-run requested" in msg for msg in result.messages)


@pytest.mark.asyncio
async def test_password_strength_validation_failure(
    test_env_harness: Any,
) -> None:
    """Weak passwords fail with domain validation error before user creation."""
    *_, service = test_env_harness

    config = PilotOnboardingConfig(
        environment="staging",
        owner_email="weakpass@example.com",
        owner_first_name="Weak",
        owner_last_name="Pass",
        business_legal_name="Weak Corp",
        password="weak",
    )

    with pytest.raises(PilotOnboardingValidationError) as exc_info:
        await service.execute(config)

    assert "Password does not meet strength rules" in str(exc_info.value)


@pytest.mark.asyncio
async def test_password_hashing_and_secret_redaction(
    test_env_harness: Any,
) -> None:
    """Password is never stored in plaintext and is verifiable with Argon2id."""
    users, *_, service = test_env_harness

    config = PilotOnboardingConfig(
        environment="staging",
        owner_email="security@example.com",
        owner_first_name="Sec",
        owner_last_name="Audit",
        business_legal_name="Security First Ltd",
        password=VALID_PASSWORD,
    )

    result = await service.execute(config)
    stored_user = users.users["security@example.com"]
    cred = users.credentials[stored_user.id]

    # Verification using Argon2id hasher
    hasher = PasswordHasher(type=Type.ID)
    assert hasher.verify(cred.password_hash, VALID_PASSWORD) is True

    # Ensure result contains no secret
    assert VALID_PASSWORD not in str(result)
    assert "password" not in result.__dict__


def test_cli_argument_parser_flags() -> None:
    """CLI argument parser correctly parses arguments and flags."""
    parser = build_argument_parser()
    args = parser.parse_args([
        "--env", "staging",
        "--email", "owner@apex.in",
        "--first-name", "Priya",
        "--last-name", "Sharma",
        "--legal-name", "Apex Logistics Ltd",
        "--activate",
        "--dry-run",
    ])

    assert args.environment == "staging"
    assert args.owner_email == "owner@apex.in"
    assert args.owner_first_name == "Priya"
    assert args.owner_last_name == "Sharma"
    assert args.business_legal_name == "Apex Logistics Ltd"
    assert args.activate_owner is True
    assert args.dry_run is True


def test_cli_main_refuses_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Main CLI entrypoint exits with 1 when production is targeted."""
    monkeypatch.delenv("TAXPILOT_ENVIRONMENT", raising=False)
    exit_code = main([
        "--env", "production",
        "--email", "owner@apex.in",
        "--first-name", "Priya",
        "--last-name", "Sharma",
        "--legal-name", "Apex Logistics Ltd",
    ])
    assert exit_code == 1


def test_cli_main_refuses_missing_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Main CLI entrypoint exits with 1 when environment is omitted."""
    monkeypatch.delenv("TAXPILOT_ENVIRONMENT", raising=False)
    monkeypatch.delenv("TAXPILOT_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    exit_code = main([
        "--email", "owner@apex.in",
        "--first-name", "Priya",
        "--last-name", "Sharma",
        "--legal-name", "Apex Logistics Ltd",
    ])
    assert exit_code == 1


@pytest.mark.asyncio
async def test_live_environment_is_strictly_refused(
    test_env_harness: Any,
) -> None:
    """Execution targeting 'live' is refused immediately."""
    *_, service = test_env_harness

    config = PilotOnboardingConfig(
        environment="live",
        owner_email="owner@live.com",
        owner_first_name="Live",
        owner_last_name="Owner",
        business_legal_name="Live Corp",
        password=VALID_PASSWORD,
    )

    with pytest.raises(PilotOnboardingEnvironmentError) as exc_info:
        await service.execute(config)

    assert "strictly prohibited in 'live'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_conflicting_environment_sources_refused(
    test_env_harness: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Conflicting environment values among CLI/config and env vars fail closed."""
    *_, service = test_env_harness

    monkeypatch.setenv("ENVIRONMENT", "development")

    config = PilotOnboardingConfig(
        environment="staging",
        owner_email="owner@staging.com",
        owner_first_name="Staging",
        owner_last_name="Owner",
        business_legal_name="Staging Corp",
        password=VALID_PASSWORD,
    )

    with pytest.raises(PilotOnboardingEnvironmentError) as exc_info:
        await service.execute(config)

    assert "Conflicting environment configuration" in str(exc_info.value)
    assert "target is 'staging'" in str(exc_info.value)
    assert "'ENVIRONMENT' is 'development'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_env_var_production_rejected_even_if_cli_specifies_staging(
    test_env_harness: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setting TAXPILOT_ENV to production causes immediate rejection."""
    *_, service = test_env_harness

    monkeypatch.setenv("TAXPILOT_ENV", "production")

    config = PilotOnboardingConfig(
        environment="staging",
        owner_email="owner@staging.com",
        owner_first_name="Staging",
        owner_last_name="Owner",
        business_legal_name="Staging Corp",
        password=VALID_PASSWORD,
    )

    with pytest.raises(PilotOnboardingEnvironmentError) as exc_info:
        await service.execute(config)

    assert "indicates prohibited environment 'production'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_staging_silent_fallback_to_default_db_rejected(
    test_env_harness: Any,
) -> None:
    """Staging environment cannot silently fall back to default development database."""
    *_, uow, _ = test_env_harness

    # Service with staging environment but unconfigured/default development database
    settings = Settings(
        environment="staging",
        identity_token_secret_key="a" * 32,
        database_url=DEFAULT_DATABASE_URL,
    )
    service = PilotOnboardingService(
        unit_of_work_factory=lambda: uow,
        settings=settings,
    )

    config = PilotOnboardingConfig(
        environment="staging",
        owner_email="owner@staging.com",
        owner_first_name="Staging",
        owner_last_name="Owner",
        business_legal_name="Staging Corp",
        password=VALID_PASSWORD,
    )

    with pytest.raises(PilotOnboardingEnvironmentError) as exc_info:
        await service.execute(config)

    assert (
        "cannot silently fall back to default development database"
        in str(exc_info.value)
    )


@pytest.mark.asyncio
async def test_production_database_url_rejected(
    test_env_harness: Any,
) -> None:
    """Database URL with prod/live keywords is rejected regardless of target."""
    *_, uow, _ = test_env_harness

    settings = Settings(
        environment="staging",
        identity_token_secret_key="a" * 32,
        database_url="postgresql+asyncpg://admin:secret@prod-db.internal:5432/taxpilot_prod",
    )
    service = PilotOnboardingService(
        unit_of_work_factory=lambda: uow,
        settings=settings,
    )

    config = PilotOnboardingConfig(
        environment="staging",
        owner_email="owner@staging.com",
        owner_first_name="Staging",
        owner_last_name="Owner",
        business_legal_name="Staging Corp",
        password=VALID_PASSWORD,
    )

    with pytest.raises(PilotOnboardingEnvironmentError) as exc_info:
        await service.execute(config)

    assert "targets prohibited 'prod' database" in str(exc_info.value)
    assert "secret" not in str(exc_info.value)  # Credential is masked


def test_config_password_repr_is_redacted() -> None:
    """Password is excluded from repr() and str() of PilotOnboardingConfig."""
    secret = "TopSecretPassword123!"
    config = PilotOnboardingConfig(
        environment="staging",
        owner_email="owner@example.com",
        owner_first_name="Test",
        owner_last_name="User",
        business_legal_name="Test Business Ltd",
        password=secret,
    )

    assert secret not in repr(config)
    assert secret not in str(config)


@pytest.mark.asyncio
async def test_existing_accounts_validation_duplicate_code_fails(
    test_env_harness: Any,
) -> None:
    """Existing Chart of Accounts with duplicate account codes fails validation."""
    *_, chart, _, uow, service = test_env_harness

    biz_id = uuid.uuid4()
    # Pre-populate chart with duplicate account codes
    chart.accounts.append(
        Account(
            id=uuid.uuid4(),
            business_id=biz_id,
            account_code="1000",
            account_name="Cash 1",
            account_type_id=uuid.uuid4(),
            is_system=True,
            is_active=True,
        )
    )
    chart.accounts.append(
        Account(
            id=uuid.uuid4(),
            business_id=biz_id,
            account_code="1000",
            account_name="Cash 2 (Duplicate)",
            account_type_id=uuid.uuid4(),
            is_system=True,
            is_active=True,
        )
    )

    with pytest.raises(PilotOnboardingValidationError) as exc_info:
        service._validate_existing_chart_of_accounts(chart.accounts, biz_id)

    assert "duplicate account code: '1000'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_existing_accounts_validation_missing_core_accounts_fails(
    test_env_harness: Any,
) -> None:
    """Existing Chart missing required core control accounts fails validation."""
    *_, chart, _, uow, service = test_env_harness

    biz_id = uuid.uuid4()
    # Pre-populate chart with only 1 account, missing 1020, 2000, 3000, 4000
    chart.accounts.append(
        Account(
            id=uuid.uuid4(),
            business_id=biz_id,
            account_code="1000",
            account_name="Cash",
            account_type_id=uuid.uuid4(),
            is_system=True,
            is_active=True,
        )
    )

    with pytest.raises(PilotOnboardingValidationError) as exc_info:
        service._validate_existing_chart_of_accounts(chart.accounts, biz_id)

    assert "Missing required core account codes" in str(exc_info.value)


@pytest.mark.asyncio
async def test_existing_accounts_validation_cross_tenant_account_fails(
    test_env_harness: Any,
) -> None:
    """Existing account belonging to another tenant fails validation immediately."""
    *_, chart, _, uow, service = test_env_harness

    biz_id = uuid.uuid4()
    foreign_biz_id = uuid.uuid4()

    chart.accounts.append(
        Account(
            id=uuid.uuid4(),
            business_id=foreign_biz_id,
            account_code="1000",
            account_name="Foreign Cash",
            account_type_id=uuid.uuid4(),
            is_system=True,
            is_active=True,
        )
    )

    with pytest.raises(PilotOnboardingConflictException) as exc_info:
        service._validate_existing_chart_of_accounts(chart.accounts, biz_id)

    assert "belongs to business" in str(exc_info.value)


