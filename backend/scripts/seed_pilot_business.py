"""Administrative pilot onboarding command.

Orchestrates controlled onboarding for a single pilot business and owner:
- Locates or creates the owner user account with Argon2id credentials.
- Optionally activates the owner user account when explicitly requested.
- Locates or creates the business entity.
- Establishes owner membership without silently overriding existing ownership.
- Provisions default Chart of Accounts idempotently without duplicating accounts.
- Enforces strict environment boundaries, refusing execution against production.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from argon2 import PasswordHasher
from argon2.low_level import Type

from app.common.unit_of_work.sqlalchemy_uow import SQLAlchemyUnitOfWork
from app.core.config import Settings, get_settings, mask_connection_string
from app.core.database import get_session_factory, initialize_database
from app.modules.accounting.chart_of_accounts.models import Account
from app.modules.accounting.chart_of_accounts.services import (
    ChartInitializerService,
)
from app.modules.business.models import (
    Business,
    BusinessMembership,
    BusinessType,
)
from app.modules.business.schemas import CreateBusinessRequest
from app.modules.business.validators import (
    validate_business_email,
    validate_business_name,
    validate_business_phone,
)
from app.modules.identity.models import IdentityRole, IdentityUser, UserStatus
from app.modules.identity.schemas import CreateUserRequest, UpdateUserRequest
from app.modules.identity.validators import (
    normalize_and_validate_email,
    validate_password_strength,
    validate_person_name,
)

OWNER_ROLE = "owner"
DEFAULT_MEMBER_ROLE = "member"
ALLOWED_ENVIRONMENTS = {"development", "testing", "staging"}
PROHIBITED_ENVIRONMENTS = {"production", "prod", "live"}
DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://taxpilot:taxpilot@localhost:5432/taxpilot"
)


class PilotOnboardingError(Exception):
    """Base exception for pilot onboarding failures."""


class PilotOnboardingEnvironmentError(PilotOnboardingError):
    """Raised when environment configuration is missing, ambiguous, or prohibited."""


class PilotOnboardingConflictException(PilotOnboardingError):
    """Raised when existing database records conflict with the onboarding request."""


class PilotOnboardingValidationError(PilotOnboardingError):
    """Raised when input parameters fail domain validation rules."""


@dataclass(frozen=True)
class PilotOnboardingConfig:
    """Configuration parameters for pilot business onboarding."""

    environment: str
    owner_email: str
    owner_first_name: str
    owner_last_name: str
    business_legal_name: str
    owner_display_name: str | None = None
    business_trade_name: str | None = None
    business_type: BusinessType = BusinessType.PRIVATE_LIMITED
    business_email: str | None = None
    business_phone: str | None = None
    activate_owner: bool = False
    dry_run: bool = False
    password: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class PilotOnboardingResult:
    """Summary of operations performed during pilot onboarding."""

    success: bool
    user_id: uuid.UUID
    user_email: str
    user_status: str
    user_created: bool
    user_activated: bool
    business_id: uuid.UUID
    business_legal_name: str
    business_created: bool
    membership_created: bool
    membership_role: str
    accounts_initialized: int
    accounts_already_present: int
    dry_run: bool
    messages: list[str] = field(default_factory=list)


class ChartInitializerProtocol(Protocol):
    """Protocol for chart initializer dependency."""

    async def initialize_default_chart(
        self,
        business_id: uuid.UUID,
        uow: Any,
    ) -> list[Account]:
        """Initialize default chart accounts for a business."""
        ...


class PasswordHasherProtocol(Protocol):
    """Protocol for password hashing."""

    def hash(self, password: str) -> str:
        """Hash a plain text password."""
        ...


class PilotOnboardingService:
    """Service orchestrating pilot onboarding within a transactional boundary."""

    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], Any],
        chart_initializer: ChartInitializerProtocol | None = None,
        password_hasher: PasswordHasherProtocol | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialize the service with injected dependencies."""
        self._uow_factory = unit_of_work_factory
        self._chart_initializer = chart_initializer or ChartInitializerService()
        self._hasher = password_hasher or PasswordHasher(type=Type.ID)
        self._settings = settings or get_settings()

    async def execute(self, config: PilotOnboardingConfig) -> PilotOnboardingResult:
        """Execute the onboarding process within a single unit of work."""
        self._validate_environment(config.environment)
        normalized_email = self._validate_inputs(config)

        messages: list[str] = []

        async with self._uow_factory() as uow:
            # 1. Process User
            user, user_created, user_activated = await self._process_user(
                uow=uow,
                config=config,
                normalized_email=normalized_email,
                messages=messages,
            )

            # 2. Process Business
            business, business_created = await self._process_business(
                uow=uow,
                config=config,
                messages=messages,
            )

            # 3. Process Membership
            membership_created, membership_role = await self._process_membership(
                uow=uow,
                business=business,
                user=user,
                business_created=business_created,
                messages=messages,
            )

            # 4. Process Chart of Accounts
            accounts_initialized, accounts_present = (
                await self._process_chart_of_accounts(
                    uow=uow,
                    business=business,
                    messages=messages,
                )
            )

            # 5. Commit or Dry-Run Rollback
            if config.dry_run:
                await uow.rollback()
                messages.append(
                    "Dry-run requested: database changes were rolled back."
                )
            else:
                await uow.commit()
                messages.append("All onboarding changes committed successfully.")

            user_status_str = str(
                user.status.value
                if hasattr(user.status, "value")
                else user.status
            )

            return PilotOnboardingResult(
                success=True,
                user_id=user.id,
                user_email=user.email,
                user_status=user_status_str,
                user_created=user_created,
                user_activated=user_activated,
                business_id=business.id,
                business_legal_name=business.legal_name,
                business_created=business_created,
                membership_created=membership_created,
                membership_role=membership_role,
                accounts_initialized=accounts_initialized,
                accounts_already_present=accounts_present,
                dry_run=config.dry_run,
                messages=messages,
            )

    def _validate_environment(self, environment: str) -> None:
        """Enforce environment boundary rules and fail closed on production."""
        cleaned_env = (environment or "").strip().lower()
        if not cleaned_env:
            raise PilotOnboardingEnvironmentError(
                "Target environment must be explicitly provided "
                "(e.g. 'staging', 'development')."
            )

        if cleaned_env in PROHIBITED_ENVIRONMENTS:
            raise PilotOnboardingEnvironmentError(
                f"Pilot onboarding is strictly prohibited in "
                f"'{cleaned_env}' environment."
            )

        if cleaned_env not in ALLOWED_ENVIRONMENTS:
            raise PilotOnboardingEnvironmentError(
                f"Unknown target environment '{cleaned_env}'. "
                f"Must be one of: {sorted(ALLOWED_ENVIRONMENTS)}."
            )

        self._validate_environment_sources(cleaned_env)
        self._validate_database_target(cleaned_env)

    def _validate_environment_sources(self, cleaned_env: str) -> None:
        """Verify all configuration sources agree and do not specify production."""
        env_sources: dict[str, str | None] = {
            "CLI/config": cleaned_env,
            "TAXPILOT_ENVIRONMENT": os.environ.get("TAXPILOT_ENVIRONMENT"),
            "TAXPILOT_ENV": os.environ.get("TAXPILOT_ENV"),
            "ENVIRONMENT": os.environ.get("ENVIRONMENT"),
            "settings.environment": getattr(self._settings, "environment", None),
        }

        for source_name, raw_val in env_sources.items():
            if not raw_val:
                continue
            val = str(raw_val).strip().lower()
            if val in PROHIBITED_ENVIRONMENTS:
                raise PilotOnboardingEnvironmentError(
                    f"Environment source '{source_name}' indicates prohibited "
                    f"environment '{val}'."
                )
            if source_name != "CLI/config" and val != cleaned_env:
                raise PilotOnboardingEnvironmentError(
                    f"Conflicting environment configuration: target is "
                    f"'{cleaned_env}', but '{source_name}' is '{val}'."
                )

    def _validate_database_target(self, cleaned_env: str) -> None:
        """Ensure database URL matches the target environment and avoids production."""
        db_url = getattr(self._settings, "database_url", "")
        if not db_url:
            return

        db_url_lower = db_url.lower()
        for forbidden in ("prod", "production", "live"):
            if (
                f"/{forbidden}" in db_url_lower
                or f"_{forbidden}" in db_url_lower
                or f"-{forbidden}" in db_url_lower
                or f".{forbidden}" in db_url_lower
                or f"@{forbidden}" in db_url_lower
                or f":{forbidden}" in db_url_lower
            ):
                masked = mask_connection_string(db_url)
                raise PilotOnboardingEnvironmentError(
                    f"Database connection string targets prohibited "
                    f"'{forbidden}' database: '{masked}'."
                )

        if cleaned_env == "staging" and (
            db_url == DEFAULT_DATABASE_URL
            or "localhost:5432/taxpilot" in db_url_lower
            or "127.0.0.1:5432/taxpilot" in db_url_lower
            or db_url_lower.endswith("/taxpilot")
            or "_dev" in db_url_lower
            or "-dev" in db_url_lower
        ):
            raise PilotOnboardingEnvironmentError(
                "Staging environment cannot silently fall back to default development "
                "database. An explicit staging database target must be configured."
            )

        if cleaned_env == "development" and "staging" in db_url_lower:
            raise PilotOnboardingEnvironmentError(
                "Development environment cannot target a staging database."
            )

    def _validate_inputs(self, config: PilotOnboardingConfig) -> str:
        """Validate input parameters using canonical domain rules."""
        try:
            email = normalize_and_validate_email(config.owner_email)
        except ValueError as exc:
            raise PilotOnboardingValidationError(
                f"Invalid owner email: {exc}"
            ) from exc

        try:
            validate_person_name(
                config.owner_first_name, field_name="first_name", max_length=100
            )
            validate_person_name(
                config.owner_last_name, field_name="last_name", max_length=100
            )
            if config.owner_display_name:
                validate_person_name(
                    config.owner_display_name,
                    field_name="display_name",
                    max_length=150,
                )
        except ValueError as exc:
            raise PilotOnboardingValidationError(
                f"Invalid owner name: {exc}"
            ) from exc

        try:
            validate_business_name(config.business_legal_name)
        except ValueError as exc:
            raise PilotOnboardingValidationError(
                f"Invalid business legal name: {exc}"
            ) from exc

        if config.business_email:
            try:
                validate_business_email(config.business_email)
            except ValueError as exc:
                raise PilotOnboardingValidationError(
                    f"Invalid business email: {exc}"
                ) from exc

        if config.business_phone:
            try:
                validate_business_phone(config.business_phone)
            except ValueError as exc:
                raise PilotOnboardingValidationError(
                    f"Invalid business phone: {exc}"
                ) from exc

        return email

    async def _process_user(
        self,
        *,
        uow: Any,
        config: PilotOnboardingConfig,
        normalized_email: str,
        messages: list[str],
    ) -> tuple[IdentityUser, bool, bool]:
        """Locate or create the owner account and optionally activate it."""
        user = await uow.users.get_by_email(normalized_email)
        user_created = False
        user_activated = False

        if user is None:
            if not config.password:
                raise PilotOnboardingValidationError(
                    f"Password is required to create new owner account "
                    f"'{normalized_email}'."
                )
            try:
                validate_password_strength(config.password)
            except ValueError as exc:
                raise PilotOnboardingValidationError(
                    f"Password does not meet strength rules: {exc}"
                ) from exc

            password_hash = self._hasher.hash(config.password)
            display_name = (
                config.owner_display_name.strip()
                if config.owner_display_name
                else None
            )
            user_req = CreateUserRequest(
                email=normalized_email,
                first_name=config.owner_first_name.strip(),
                last_name=config.owner_last_name.strip(),
                display_name=display_name,
                password=config.password,
            )
            user = await uow.users.create_user(user_req)
            await uow.users.create_credential(
                user_id=user.id, password_hash=password_hash
            )

            member_role = await self._get_or_create_member_role(uow)
            await uow.roles.assign_role(user_id=user.id, role_id=member_role.id)
            user_created = True
            messages.append(
                f"Created new identity user: {normalized_email} (ID: {user.id})"
            )
        else:
            messages.append(
                f"Located existing identity user: {normalized_email} (ID: {user.id})"
            )
            messages.append(
                f"Existing credentials preserved for {normalized_email}; "
                f"password modification is prohibited."
            )

        # Activation handling
        status_val = (
            user.status.value
            if isinstance(user.status, UserStatus)
            else str(user.status)
        )

        if config.activate_owner:
            if status_val == UserStatus.PENDING.value:
                user = await uow.users.update_user(
                    user,
                    UpdateUserRequest(status=UserStatus.ACTIVE),
                )
                user_activated = True
                messages.append(
                    f"Explicitly activated user account {normalized_email} "
                    f"(status: ACTIVE)."
                )
            elif status_val == UserStatus.ACTIVE.value:
                messages.append(
                    f"User account {normalized_email} is already ACTIVE."
                )
            else:
                messages.append(
                    f"User account {normalized_email} has non-pending status "
                    f"'{status_val}'; status unchanged."
                )
        else:
            messages.append(
                f"User account {normalized_email} status: '{status_val}'. "
                f"Activation was not requested (--activate not specified)."
            )

        return user, user_created, user_activated

    async def _process_business(
        self,
        *,
        uow: Any,
        config: PilotOnboardingConfig,
        messages: list[str],
    ) -> tuple[Business, bool]:
        """Locate or create the business entity aggregate."""
        business = await uow.businesses.get_by_legal_name(
            config.business_legal_name.strip()
        )
        business_created = False

        if business is None:
            trade_name = (
                config.business_trade_name.strip()
                if config.business_trade_name
                else None
            )
            req = CreateBusinessRequest(
                legal_name=config.business_legal_name.strip(),
                trade_name=trade_name,
                business_type=config.business_type,
                business_email=config.business_email,
                business_phone=config.business_phone,
            )
            business = await uow.businesses.create_business(req)
            business_created = True
            messages.append(
                f"Created new business: '{business.legal_name}' "
                f"(ID: {business.id})"
            )
        else:
            messages.append(
                f"Located existing business: '{business.legal_name}' "
                f"(ID: {business.id})"
            )

        return business, business_created

    async def _process_membership(
        self,
        *,
        uow: Any,
        business: Business,
        user: IdentityUser,
        business_created: bool,
        messages: list[str],
    ) -> tuple[bool, str]:
        """Establish or verify owner business membership safely."""
        if business_created:
            await uow.business_memberships.add_member(
                business_id=business.id,
                user_id=user.id,
                role=OWNER_ROLE,
            )
            messages.append(
                f"Assigned owner role to user {user.email} for business "
                f"'{business.legal_name}'."
            )
            return True, OWNER_ROLE

        memberships: list[BusinessMembership] = (
            await uow.business_memberships.get_members(business.id)
        )
        existing_owner = next(
            (m for m in memberships if m.role == OWNER_ROLE),
            None,
        )

        if existing_owner is not None:
            if existing_owner.user_id != user.id:
                raise PilotOnboardingConflictException(
                    f"Business '{business.legal_name}' already exists and is owned "
                    f"by a different user (User ID: {existing_owner.user_id}). "
                    f"Silently overwriting or reassigning ownership is prohibited."
                )
            messages.append(
                f"Verified existing owner membership for user {user.email}."
            )
            return False, OWNER_ROLE

        user_membership = next(
            (m for m in memberships if m.user_id == user.id),
            None,
        )
        if user_membership is not None:
            if user_membership.role != OWNER_ROLE:
                raise PilotOnboardingConflictException(
                    f"User {user.email} is already a member of "
                    f"'{business.legal_name}' with non-owner role "
                    f"'{user_membership.role}'. Role upgrade requires review."
                )
            return False, OWNER_ROLE

        await uow.business_memberships.add_member(
            business_id=business.id,
            user_id=user.id,
            role=OWNER_ROLE,
        )
        messages.append(
            f"Established missing owner membership for user {user.email}."
        )
        return True, OWNER_ROLE

    async def _process_chart_of_accounts(
        self,
        *,
        uow: Any,
        business: Business,
        messages: list[str],
    ) -> tuple[int, int]:
        """Initialize or verify standard Chart of Accounts without duplication."""
        existing_accounts = await uow.chart_of_accounts.list_accounts(
            business_id=business.id
        )
        if existing_accounts:
            self._validate_existing_chart_of_accounts(
                existing_accounts, business.id
            )
            count = len(existing_accounts)
            messages.append(
                f"Chart of Accounts validated: {count} accounts found with required "
                f"core structure. Skipping initialization."
            )
            return 0, count

        accounts = await self._chart_initializer.initialize_default_chart(
            business.id, uow
        )
        count = len(accounts)
        messages.append(
            f"Initialized standard Chart of Accounts: {count} accounts created."
        )
        return count, 0

    def _validate_existing_chart_of_accounts(
        self,
        accounts: list[Account],
        business_id: uuid.UUID,
    ) -> None:
        """Validate integrity and core invariants of an existing Chart of Accounts."""
        if not accounts:
            return

        seen_codes: set[str] = set()
        for acc in accounts:
            code = getattr(acc, "account_code", None)
            if not code or not str(code).strip():
                raise PilotOnboardingValidationError(
                    "Existing Chart of Accounts contains an account with an empty "
                    "code."
                )
            code_str = str(code).strip()
            if code_str in seen_codes:
                raise PilotOnboardingValidationError(
                    f"Existing Chart of Accounts contains duplicate account code: "
                    f"'{code_str}'."
                )
            seen_codes.add(code_str)

            acc_biz_id = getattr(acc, "business_id", None)
            if acc_biz_id != business_id:
                raise PilotOnboardingConflictException(
                    f"Existing account '{code_str}' belongs to business {acc_biz_id}, "
                    f"not the target business {business_id}."
                )

        required_core_codes = {"1000", "1020", "2000", "3000", "4000"}
        missing_core = required_core_codes - seen_codes
        if missing_core:
            raise PilotOnboardingValidationError(
                f"Existing Chart of Accounts is incomplete or corrupted. "
                f"Missing required core account codes: {sorted(missing_core)}."
            )

    async def _get_or_create_member_role(self, uow: Any) -> IdentityRole:
        """Return the default member role, creating it when absent."""
        member_role = await uow.roles.get_by_name(DEFAULT_MEMBER_ROLE)
        if member_role is not None:
            return member_role
        return await uow.roles.create_role(
            name=DEFAULT_MEMBER_ROLE,
            description="Default member role",
            is_system=True,
        )


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser with strict environment options."""
    parser = argparse.ArgumentParser(
        description="Administrative pilot onboarding command for TaxPilot AI.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--env",
        dest="environment",
        type=str,
        default=(
            os.environ.get("TAXPILOT_ENVIRONMENT")
            or os.environ.get("TAXPILOT_ENV")
            or os.environ.get("ENVIRONMENT")
        ),
        help="Target runtime environment (development, testing, staging).",
    )
    parser.add_argument(
        "--email",
        dest="owner_email",
        type=str,
        required=True,
        help="Owner email address.",
    )
    parser.add_argument(
        "--first-name",
        dest="owner_first_name",
        type=str,
        required=True,
        help="Owner first name.",
    )
    parser.add_argument(
        "--last-name",
        dest="owner_last_name",
        type=str,
        required=True,
        help="Owner last name.",
    )
    parser.add_argument(
        "--display-name",
        dest="owner_display_name",
        type=str,
        default=None,
        help="Optional owner display name.",
    )
    parser.add_argument(
        "--legal-name",
        dest="business_legal_name",
        type=str,
        required=True,
        help="Business legal registered name.",
    )
    parser.add_argument(
        "--trade-name",
        dest="business_trade_name",
        type=str,
        default=None,
        help="Optional trade name.",
    )
    parser.add_argument(
        "--business-type",
        dest="business_type",
        type=str,
        choices=[t.value for t in BusinessType],
        default=BusinessType.PRIVATE_LIMITED.value,
        help="Organization structure.",
    )
    parser.add_argument(
        "--business-email",
        dest="business_email",
        type=str,
        default=None,
        help="Optional primary business email.",
    )
    parser.add_argument(
        "--business-phone",
        dest="business_phone",
        type=str,
        default=None,
        help="Optional business phone in E.164 format (+91...).",
    )
    parser.add_argument(
        "--activate",
        dest="activate_owner",
        action="store_true",
        default=False,
        help="Explicitly activate owner account (sets status to ACTIVE).",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="Validate and rehearse without committing database changes.",
    )
    return parser


def prompt_password_securely(email: str) -> str:
    """Prompt the operator securely for owner password without echoing or logging."""
    env_password = os.environ.get("TAXPILOT_PILOT_OWNER_PASSWORD")
    if env_password:
        return env_password

    if not sys.stdin.isatty():
        raise PilotOnboardingValidationError(
            "Password must be provided via TAXPILOT_PILOT_OWNER_PASSWORD in "
            "non-interactive sessions."
        )

    print(f"Provisioning password for new owner account: {email}")
    pwd1 = getpass.getpass("Enter owner password (minimum 12 chars): ")
    pwd2 = getpass.getpass("Confirm owner password: ")
    if pwd1 != pwd2:
        raise PilotOnboardingValidationError("Passwords do not match.")
    return pwd1


async def run_onboarding(config: PilotOnboardingConfig) -> PilotOnboardingResult:
    """Initialize database engine and execute onboarding within real UoW factory."""
    settings = get_settings()
    initialize_database(settings)
    session_factory = get_session_factory()

    def uow_factory() -> SQLAlchemyUnitOfWork:
        return SQLAlchemyUnitOfWork(session_factory)

    service = PilotOnboardingService(
        unit_of_work_factory=uow_factory,
        settings=settings,
    )
    return await service.execute(config)


def print_result_summary(result: PilotOnboardingResult) -> None:
    """Print sanitized summary of the onboarding execution without leaking secrets."""
    print("\n" + "=" * 60)
    print("TAXPILOT AI — PILOT ONBOARDING EXECUTION SUMMARY")
    print("=" * 60)
    status_label = "DRY-RUN SUCCESS" if result.dry_run else "SUCCESS"
    user_created_str = "YES" if result.user_created else "NO (already existed)"
    user_activated_str = "YES" if result.user_activated else "NO"
    biz_created_str = "YES" if result.business_created else "NO (already existed)"
    membership_str = "CREATED" if result.membership_created else "EXISTING"

    print(f"Status:               {status_label}")
    print(f"Owner Email:          {result.user_email}")
    print(f"Owner User ID:        {result.user_id}")
    print(f"Account Status:       {result.user_status}")
    print(f"User Created:         {user_created_str}")
    print(f"User Activated:       {user_activated_str}")
    print("-" * 60)
    print(f"Business Legal Name:  {result.business_legal_name}")
    print(f"Business ID:          {result.business_id}")
    print(f"Business Created:     {biz_created_str}")
    print(f"Owner Membership:     {membership_str}")
    print(f"Membership Role:      {result.membership_role}")
    print("-" * 60)
    print(f"Accounts Initialized: {result.accounts_initialized}")
    print(f"Accounts Existing:    {result.accounts_already_present}")
    print("=" * 60)
    print("Execution Log:")
    for msg in result.messages:
        print(f"  • {msg}")
    print("=" * 60 + "\n")


def main(argv: list[str] | None = None) -> int:
    """Entry point for the administrative onboarding script."""
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    target_env = (args.environment or "").strip().lower()
    if not target_env:
        print(
            "ERROR: Missing target environment. Pass "
            "--env <staging|development|testing> or set TAXPILOT_ENVIRONMENT.",
            file=sys.stderr,
        )
        return 1

    if target_env in PROHIBITED_ENVIRONMENTS:
        print(
            f"ERROR: Execution against prohibited environment '{target_env}' "
            f"is refused.",
            file=sys.stderr,
        )
        return 1

    try:
        # Secure password resolution
        password = prompt_password_securely(args.owner_email)

        config = PilotOnboardingConfig(
            environment=target_env,
            owner_email=args.owner_email,
            owner_first_name=args.owner_first_name,
            owner_last_name=args.owner_last_name,
            owner_display_name=args.owner_display_name,
            business_legal_name=args.business_legal_name,
            business_trade_name=args.business_trade_name,
            business_type=BusinessType(args.business_type),
            business_email=args.business_email,
            business_phone=args.business_phone,
            activate_owner=args.activate_owner,
            dry_run=args.dry_run,
            password=password,
        )

        result = asyncio.run(run_onboarding(config))
        print_result_summary(result)
        return 0

    except PilotOnboardingError as exc:
        print(f"\n[ONBOARDING FAILED]: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"\n[UNEXPECTED ERROR]: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
