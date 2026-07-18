"""Tests for GST Foundation module."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Self, cast

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.common.events import Event, EventDispatcher
from app.common.pagination import Page, PaginationParams
from app.main import create_app
from app.modules.gst.api.dependencies import (
    get_gst_registration_service,
    get_gst_unit_of_work,
)
from app.modules.gst.events import GSTRegistrationCreatedEvent
from app.modules.gst.exceptions import GSTDuplicateRegistrationException
from app.modules.gst.models import GSTRegistration, GSTRegistrationType
from app.modules.gst.schemas import (
    GSTRegistrationCreate,
    GSTRegistrationUpdate,
    GSTTaxRateCreate,
    HSNCodeCreate,
    SACCodeCreate,
)
from app.modules.gst.services import GSTRegistrationService
from app.modules.gst.services.registration_service import GSTRegistrationUnitOfWork
from app.modules.identity.dependencies.current_user import get_current_user
from app.modules.identity.models import IdentityUser, UserStatus

HTTP_CREATED = 201
HTTP_OK = 200
HTTP_BAD_REQUEST = 400


class CapturingEventDispatcher(EventDispatcher):
    """Event dispatcher that records published events."""

    def __init__(self) -> None:
        """Initialize captured events."""
        super().__init__()
        self.events: list[Event] = []

    async def dispatch(self, event: Event) -> None:
        """Capture and dispatch an event."""
        self.events.append(event)
        await super().dispatch(event)


class FakeMembershipRepository:
    """Fake business membership repository."""

    async def is_member(self, *, business_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Return successful membership."""
        _ = business_id
        _ = user_id
        return True


class FakeGSTRegistrationRepository:
    """Fake GST registration repository."""

    def __init__(self) -> None:
        """Initialize registrations."""
        self.registrations: list[GSTRegistration] = []

    async def create(
        self,
        request: GSTRegistrationCreate,
        *,
        business_id: uuid.UUID,
    ) -> GSTRegistration:
        """Create GST registration."""
        registration = GSTRegistration(
            id=uuid.uuid4(),
            business_id=business_id,
            **request.model_dump(),
        )
        self.registrations.append(registration)
        return registration

    async def update(
        self,
        registration: GSTRegistration,
        request: GSTRegistrationUpdate,
    ) -> GSTRegistration:
        """Update GST registration."""
        for field_name, value in request.model_dump(exclude_unset=True).items():
            setattr(registration, field_name, value)
        return registration

    async def deactivate(self, registration: GSTRegistration) -> GSTRegistration:
        """Deactivate GST registration."""
        registration.is_active = False
        return registration

    async def get_by_id(self, registration_id: uuid.UUID) -> GSTRegistration | None:
        """Return registration by UUID."""
        return next(
            (
                registration
                for registration in self.registrations
                if registration.id == registration_id
            ),
            None,
        )

    async def get_active_by_business(
        self,
        business_id: uuid.UUID,
    ) -> GSTRegistration | None:
        """Return active registration by business."""
        return next(
            (
                registration
                for registration in self.registrations
                if registration.business_id == business_id and registration.is_active
            ),
            None,
        )

    async def list(
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
    ) -> Page[GSTRegistration]:
        """List registrations by business."""
        params = pagination or PaginationParams()
        items = [
            registration
            for registration in self.registrations
            if registration.business_id == business_id
        ]
        return Page.create(items=items, total=len(items), params=params)


class FakeGSTUnitOfWork:
    """Fake GST Unit of Work."""

    def __init__(self, repository: FakeGSTRegistrationRepository) -> None:
        """Initialize fake Unit of Work."""
        self.gst_registrations = repository
        self.business_memberships = FakeMembershipRepository()
        self.committed = False

    async def __aenter__(self) -> Self:
        """Enter fake transaction."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit fake transaction."""
        _ = exc_type
        _ = exc
        _ = traceback

    async def commit(self) -> None:
        """Mark transaction committed."""
        self.committed = True


def build_registration_request() -> GSTRegistrationCreate:
    """Build valid GST registration request."""
    return GSTRegistrationCreate(
        gstin="29ABCDE1234F1Z5",
        legal_name="Aarav Technologies Private Limited",
        trade_name="Aarav Tech",
        registration_type=GSTRegistrationType.REGULAR,
        state_code="29",
        registration_date=date(2026, 4, 1),
    )


def build_user() -> IdentityUser:
    """Build authenticated user."""
    return IdentityUser(
        id=uuid.uuid4(),
        email="owner@example.com",
        first_name="Aarav",
        last_name="Sharma",
        display_name="Aarav Sharma",
        status=UserStatus.ACTIVE,
    )


def test_gst_schema_validation() -> None:
    """GST schemas validate GSTIN, HSN, SAC, rates, and dates."""
    with pytest.raises(ValidationError):
        GSTRegistrationCreate(
            **build_registration_request().model_dump(exclude={"gstin"}),
            gstin="invalid",
        )
    with pytest.raises(ValidationError):
        HSNCodeCreate(code="12A4", description="Bad HSN")
    with pytest.raises(ValidationError):
        SACCodeCreate(code="12345", description="Bad SAC")
    with pytest.raises(ValidationError):
        GSTTaxRateCreate(
            name="GST 101%",
            cgst_rate=Decimal("0.00"),
            sgst_rate=Decimal("0.00"),
            igst_rate=Decimal("101.00"),
            effective_from=date(2026, 4, 1),
        )
    with pytest.raises(ValidationError):
        GSTTaxRateCreate(
            name="GST 18%",
            cgst_rate=Decimal("9.00"),
            sgst_rate=Decimal("9.00"),
            igst_rate=Decimal("18.00"),
            effective_from=date(2026, 4, 1),
            effective_to=date(2026, 3, 31),
        )


@pytest.mark.asyncio
async def test_registration_service_enforces_one_active_registration() -> None:
    """GST registration service rejects duplicate active registrations."""
    repository = FakeGSTRegistrationRepository()
    dispatcher = CapturingEventDispatcher()
    uow = FakeGSTUnitOfWork(repository)
    service = GSTRegistrationService(
        unit_of_work_factory=lambda: cast(GSTRegistrationUnitOfWork, uow),
        event_dispatcher=dispatcher,
    )
    business_id = uuid.uuid4()

    response = await service.create_registration(
        build_registration_request(),
        business_id=business_id,
    )

    assert response.business_id == business_id
    assert uow.committed is True
    assert isinstance(dispatcher.events[0], GSTRegistrationCreatedEvent)
    with pytest.raises(GSTDuplicateRegistrationException):
        await service.create_registration(
            build_registration_request(),
            business_id=business_id,
        )


def test_gst_registration_api_and_openapi() -> None:
    """GST API delegates registration creation and documents endpoints."""
    app = create_app(initialize_resources=False)
    repository = FakeGSTRegistrationRepository()
    uow = FakeGSTUnitOfWork(repository)
    service = GSTRegistrationService(
        unit_of_work_factory=lambda: cast(GSTRegistrationUnitOfWork, uow),
        event_dispatcher=CapturingEventDispatcher(),
    )
    business_id = uuid.uuid4()

    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_gst_unit_of_work] = lambda: uow
    app.dependency_overrides[get_gst_registration_service] = lambda: service

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/gst/registrations",
            params={"business_id": str(business_id)},
            json=build_registration_request().model_dump(mode="json"),
        )
        invalid_response = client.post(
            "/api/v1/gst/registrations",
            params={"business_id": str(business_id)},
            json={
                **build_registration_request().model_dump(mode="json"),
                "gstin": "bad",
            },
        )
        schema = client.get("/openapi.json").json()

    assert response.status_code == HTTP_CREATED
    assert response.json()["data"]["gstin"] == "29ABCDE1234F1Z5"
    assert invalid_response.status_code == HTTP_BAD_REQUEST
    assert "/api/v1/gst/registrations" in schema["paths"]
    assert "/api/v1/gst/tax-rates" in schema["paths"]
    assert "/api/v1/gst/hsn-codes" in schema["paths"]
    assert "/api/v1/gst/sac-codes" in schema["paths"]
    assert "/api/v1/gst/settings" in schema["paths"]
