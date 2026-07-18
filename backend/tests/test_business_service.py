"""Tests for business lifecycle service."""

import uuid
from collections.abc import Callable
from datetime import date
from typing import cast

import pytest

from app.common.events import Event, EventDispatcher
from app.common.pagination import Page, PaginationParams
from app.modules.accounting.chart_of_accounts.models import (
    Account,
    AccountCategory,
    AccountType,
)
from app.modules.accounting.chart_of_accounts.services.chart_initializer import (
    ChartInitializerRepository,
)
from app.modules.business.events import (
    BusinessArchivedEvent,
    BusinessCreatedEvent,
    BusinessRestoredEvent,
    BusinessUpdatedEvent,
)
from app.modules.business.exceptions import (
    BusinessDuplicateNameException,
    BusinessNotFoundException,
)
from app.modules.business.models import (
    Business,
    BusinessAddress,
    BusinessMembership,
    BusinessSettings,
    BusinessStatus,
    BusinessTaxProfile,
    BusinessType,
    RegistrationStatus,
)
from app.modules.business.schemas import CreateBusinessRequest, UpdateBusinessRequest
from app.modules.business.services import BusinessService
from app.modules.business.services.business_service import (
    BusinessLifecycleRepository,
    BusinessMembershipLifecycleRepository,
    BusinessUnitOfWork,
)

pytestmark = pytest.mark.asyncio


class FakeBusinessRepository:
    """Fake business repository for service tests."""

    def __init__(
        self,
        *,
        business: Business | None = None,
        duplicate_name: bool = False,
        fail_create: bool = False,
    ) -> None:
        """Initialize fake behavior."""
        self.business = business
        self.duplicate_name = duplicate_name
        self.fail_create = fail_create
        self.created_request: CreateBusinessRequest | None = None
        self.updated_request: UpdateBusinessRequest | None = None

    async def create_business(
        self,
        request: CreateBusinessRequest,
        *,
        business_code: str | None = None,
    ) -> Business:
        """Create a fake business aggregate."""
        if self.fail_create:
            raise RuntimeError("create failed")
        business_id = uuid.uuid4()
        self.created_request = request
        business = Business(
            id=business_id,
            business_code=business_code,
            legal_name=request.legal_name,
            trade_name=request.trade_name,
            business_type=request.business_type,
            registration_status=request.registration_status,
            business_email=request.business_email,
            business_phone=request.business_phone,
            website=request.website,
            status=BusinessStatus.ACTIVE,
        )
        if request.address is not None:
            business.address = BusinessAddress(
                id=uuid.uuid4(),
                business_id=business_id,
                **request.address.model_dump(),
            )
        if request.settings is not None:
            business.settings = BusinessSettings(
                id=uuid.uuid4(),
                business_id=business_id,
                **request.settings.model_dump(),
            )
        if request.tax_profile is not None:
            business.tax_profile = BusinessTaxProfile(
                id=uuid.uuid4(),
                business_id=business_id,
                **request.tax_profile.model_dump(),
            )
        self.business = business
        return business

    async def get_by_id(self, business_id: uuid.UUID) -> Business | None:
        """Return the configured business."""
        if self.business is None or self.business.id != business_id:
            return None
        return self.business

    async def get_by_business_code(self, business_code: str) -> Business | None:
        """Return the configured business by code."""
        if self.business is None or self.business.business_code != business_code:
            return None
        return self.business

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        search: str | None = None,
        sort: str | None = None,
    ) -> Page[Business]:
        """Return the configured business as a page."""
        params = pagination or PaginationParams()
        items = [] if self.business is None else [self.business]
        return Page.create(items=items, total=len(items), params=params)

    async def update_business(
        self,
        business: Business,
        request: UpdateBusinessRequest,
    ) -> Business:
        """Record an update request and return the business."""
        self.updated_request = request
        update_data = request.model_dump(
            exclude_unset=True,
            exclude={"address", "settings", "tax_profile"},
        )
        for field_name, value in update_data.items():
            setattr(business, field_name, value)
        self.business = business
        return business

    async def archive_business(self, business: Business) -> Business:
        """Archive the business."""
        business.status = BusinessStatus.ARCHIVED
        self.business = business
        return business

    async def restore_business(self, business: Business) -> Business:
        """Restore the business."""
        business.status = BusinessStatus.ACTIVE
        self.business = business
        return business

    async def exists_by_name(self, legal_name: str) -> bool:
        """Return configured duplicate-name result."""
        return self.duplicate_name


class FakeBusinessMembershipRepository:
    """Fake business membership repository for service tests."""

    def __init__(self) -> None:
        """Initialize fake membership state."""
        self.memberships: list[BusinessMembership] = []

    async def add_member(
        self,
        *,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str,
    ) -> BusinessMembership:
        """Add a fake membership."""
        membership = BusinessMembership(
            id=uuid.uuid4(),
            business_id=business_id,
            user_id=user_id,
            role=role,
        )
        self.memberships.append(membership)
        return membership

    async def is_member(self, *, business_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Return whether a fake membership exists."""
        return any(
            membership.business_id == business_id and membership.user_id == user_id
            for membership in self.memberships
        )


class FakeChartRepository:
    """Fake chart repository for business service tests."""

    async def get_category_by_name(self, name: str) -> AccountCategory | None:
        """Return no category."""
        return None

    async def create_category(
        self,
        *,
        name: str,
        description: str | None = None,
    ) -> AccountCategory:
        """Create a fake category."""
        return AccountCategory(id=uuid.uuid4(), name=name, description=description)

    async def get_account_type_by_name(
        self,
        *,
        category_id: uuid.UUID,
        name: str,
    ) -> AccountType | None:
        """Return no account type."""
        return None

    async def create_account_type(
        self,
        *,
        category_id: uuid.UUID,
        name: str,
    ) -> AccountType:
        """Create a fake account type."""
        return AccountType(id=uuid.uuid4(), category_id=category_id, name=name)

    async def create_account(
        self,
        *,
        business_id: uuid.UUID,
        account_code: str,
        account_name: str,
        account_type_id: uuid.UUID,
        is_system: bool,
    ) -> Account:
        """Create a fake account."""
        return Account(
            id=uuid.uuid4(),
            business_id=business_id,
            account_code=account_code,
            account_name=account_name,
            account_type_id=account_type_id,
            is_system=is_system,
        )


class FakeChartInitializer:
    """Fake chart initializer for business service tests."""

    def __init__(self, *, fail: bool = False) -> None:
        """Initialize fake behavior."""
        self.fail = fail
        self.business_ids: list[uuid.UUID] = []

    async def initialize_default_chart(
        self,
        business_id: uuid.UUID,
        uow: object,
    ) -> list[object]:
        """Record initialization or raise configured failure."""
        if self.fail:
            raise RuntimeError("chart failed")
        self.business_ids.append(business_id)
        return []


class FakeBusinessUnitOfWork:
    """Fake Unit of Work for service tests."""

    def __init__(
        self,
        *,
        businesses: FakeBusinessRepository,
        memberships: FakeBusinessMembershipRepository,
    ) -> None:
        """Initialize fake repositories."""
        self.businesses: BusinessLifecycleRepository = businesses
        self.business_memberships: BusinessMembershipLifecycleRepository = memberships
        self.chart_of_accounts: ChartInitializerRepository = FakeChartRepository()
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> "FakeBusinessUnitOfWork":
        """Enter fake transaction scope."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Rollback uncommitted fake transactions."""
        if exc_type is not None or not self.committed:
            self.rolled_back = True

    async def commit(self) -> None:
        """Mark the fake transaction committed."""
        self.committed = True


class CapturingEventDispatcher(EventDispatcher):
    """Event dispatcher that records dispatched events."""

    def __init__(self) -> None:
        """Initialize captured events."""
        super().__init__()
        self.events: list[Event] = []

    async def dispatch(self, event: Event) -> None:
        """Record and dispatch an event."""
        self.events.append(event)
        await super().dispatch(event)


def build_create_request(
    legal_name: str = "TaxPilot Labs Private Limited",
) -> CreateBusinessRequest:
    """Build a valid create business request."""
    return CreateBusinessRequest(
        legal_name=legal_name,
        trade_name="TaxPilot Labs",
        business_type=BusinessType.PRIVATE_LIMITED,
        registration_status=RegistrationStatus.REGISTERED,
        business_email="accounts@example.com",
        business_phone="+919876543210",
        website="https://example.com",
        address={
            "address_line_1": "42 Residency Road",
            "city": "Bengaluru",
            "state": "Karnataka",
            "country": "India",
            "postal_code": "560025",
        },
        tax_profile={
            "gstin": "29ABCDE1234F1Z5",
            "pan": "ABCDE1234F",
            "financial_year_start": "2026-04-01",
            "gst_registered": True,
            "composition_scheme": False,
        },
    )


def build_business(status: BusinessStatus = BusinessStatus.ACTIVE) -> Business:
    """Build a business aggregate with nested records."""
    business_id = uuid.uuid4()
    return Business(
        id=business_id,
        legal_name="TaxPilot Labs Private Limited",
        trade_name="TaxPilot Labs",
        business_type=BusinessType.PRIVATE_LIMITED,
        registration_status=RegistrationStatus.REGISTERED,
        business_email="accounts@example.com",
        business_phone="+919876543210",
        website="https://example.com",
        status=status,
        address=BusinessAddress(
            id=uuid.uuid4(),
            business_id=business_id,
            address_line_1="42 Residency Road",
            city="Bengaluru",
            state="Karnataka",
            country="India",
            postal_code="560025",
        ),
        settings=BusinessSettings(
            id=uuid.uuid4(),
            business_id=business_id,
            currency="INR",
            timezone="Asia/Kolkata",
            date_format="DD/MM/YYYY",
            language="en",
        ),
        tax_profile=BusinessTaxProfile(
            id=uuid.uuid4(),
            business_id=business_id,
            gstin="29ABCDE1234F1Z5",
            pan="ABCDE1234F",
            financial_year_start=date(2026, 4, 1),
            gst_registered=True,
            composition_scheme=False,
        ),
    )


def build_service(
    uow: FakeBusinessUnitOfWork,
    dispatcher: CapturingEventDispatcher,
    chart_initializer: FakeChartInitializer | None = None,
) -> BusinessService:
    """Build a business service for tests."""
    unit_of_work_factory = cast(Callable[[], BusinessUnitOfWork], lambda: uow)
    return BusinessService(
        unit_of_work_factory=unit_of_work_factory,
        event_dispatcher=dispatcher,
        chart_initializer=chart_initializer or FakeChartInitializer(),
    )


async def test_create_business_creates_owner_membership_and_event() -> None:
    """Business creation creates owner membership and publishes event."""
    businesses = FakeBusinessRepository()
    memberships = FakeBusinessMembershipRepository()
    uow = FakeBusinessUnitOfWork(businesses=businesses, memberships=memberships)
    dispatcher = CapturingEventDispatcher()
    chart_initializer = FakeChartInitializer()
    service = build_service(uow, dispatcher, chart_initializer)
    owner_user_id = uuid.uuid4()

    response = await service.create_business(build_create_request(), owner_user_id)

    assert response.legal_name == "TaxPilot Labs Private Limited"
    assert response.settings is not None
    assert uow.committed is True
    assert len(memberships.memberships) == 1
    assert memberships.memberships[0].user_id == owner_user_id
    assert memberships.memberships[0].role == "owner"
    assert chart_initializer.business_ids == [response.id]
    assert isinstance(dispatcher.events[0], BusinessCreatedEvent)


async def test_duplicate_business_rolls_back() -> None:
    """Duplicate business name raises domain error and rolls back."""
    businesses = FakeBusinessRepository(duplicate_name=True)
    memberships = FakeBusinessMembershipRepository()
    uow = FakeBusinessUnitOfWork(businesses=businesses, memberships=memberships)
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(BusinessDuplicateNameException):
        await service.create_business(build_create_request(), uuid.uuid4())

    assert uow.committed is False
    assert uow.rolled_back is True
    assert memberships.memberships == []


async def test_update_business_updates_nested_records_and_event() -> None:
    """Business update mutates scalar and nested records and publishes event."""
    business = build_business()
    businesses = FakeBusinessRepository(business=business)
    memberships = FakeBusinessMembershipRepository()
    uow = FakeBusinessUnitOfWork(businesses=businesses, memberships=memberships)
    dispatcher = CapturingEventDispatcher()
    service = build_service(uow, dispatcher)

    response = await service.update_business(
        business.id,
        UpdateBusinessRequest(
            trade_name="TaxPilot",
            address={
                "address_line_1": "99 MG Road",
                "city": "Bengaluru",
                "state": "Karnataka",
                "country": "India",
                "postal_code": "560001",
            },
            settings={"currency": "INR", "timezone": "UTC", "language": "en"},
            tax_profile={
                "gstin": "29ABCDE1234F1Z5",
                "pan": "ABCDE1234F",
                "financial_year_start": "2026-04-01",
            },
        ),
    )

    assert response.trade_name == "TaxPilot"
    assert response.address is not None
    assert response.address.address_line_1 == "99 MG Road"
    assert uow.committed is True
    assert businesses.updated_request is not None
    assert isinstance(dispatcher.events[0], BusinessUpdatedEvent)


async def test_update_missing_business_raises_not_found() -> None:
    """Updating a missing business raises a domain not-found error."""
    businesses = FakeBusinessRepository()
    memberships = FakeBusinessMembershipRepository()
    uow = FakeBusinessUnitOfWork(businesses=businesses, memberships=memberships)
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(BusinessNotFoundException):
        await service.update_business(uuid.uuid4(), UpdateBusinessRequest())

    assert uow.rolled_back is True


async def test_archive_business_publishes_event() -> None:
    """Archive marks business archived, commits, and publishes event."""
    business = build_business()
    businesses = FakeBusinessRepository(business=business)
    uow = FakeBusinessUnitOfWork(
        businesses=businesses,
        memberships=FakeBusinessMembershipRepository(),
    )
    dispatcher = CapturingEventDispatcher()
    service = build_service(uow, dispatcher)

    response = await service.archive_business(business.id)

    assert response.status == BusinessStatus.ARCHIVED
    assert uow.committed is True
    assert isinstance(dispatcher.events[0], BusinessArchivedEvent)


async def test_restore_business_publishes_event() -> None:
    """Restore marks business active, commits, and publishes event."""
    business = build_business(status=BusinessStatus.ARCHIVED)
    businesses = FakeBusinessRepository(business=business)
    uow = FakeBusinessUnitOfWork(
        businesses=businesses,
        memberships=FakeBusinessMembershipRepository(),
    )
    dispatcher = CapturingEventDispatcher()
    service = build_service(uow, dispatcher)

    response = await service.restore_business(business.id)

    assert response.status == BusinessStatus.ACTIVE
    assert uow.committed is True
    assert isinstance(dispatcher.events[0], BusinessRestoredEvent)


async def test_rollback_on_failure() -> None:
    """Unit of Work rolls back when repository creation fails."""
    businesses = FakeBusinessRepository(fail_create=True)
    uow = FakeBusinessUnitOfWork(
        businesses=businesses,
        memberships=FakeBusinessMembershipRepository(),
    )
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(RuntimeError):
        await service.create_business(build_create_request(), uuid.uuid4())

    assert uow.committed is False
    assert uow.rolled_back is True


async def test_rollback_when_chart_initialization_fails() -> None:
    """Unit of Work rolls back when default chart initialization fails."""
    businesses = FakeBusinessRepository()
    uow = FakeBusinessUnitOfWork(
        businesses=businesses,
        memberships=FakeBusinessMembershipRepository(),
    )
    service = build_service(
        uow,
        CapturingEventDispatcher(),
        FakeChartInitializer(fail=True),
    )

    with pytest.raises(RuntimeError):
        await service.create_business(build_create_request(), uuid.uuid4())

    assert uow.committed is False
    assert uow.rolled_back is True
