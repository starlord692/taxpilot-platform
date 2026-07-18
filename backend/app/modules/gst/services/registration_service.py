"""GST registration service."""

import uuid
from collections.abc import Callable
from typing import Protocol

from app.common.events import EventDispatcher
from app.common.pagination import Page, PaginationParams
from app.modules.gst.events import (
    GSTRegistrationCreatedEvent,
    GSTRegistrationUpdatedEvent,
)
from app.modules.gst.exceptions import (
    GSTDuplicateRegistrationException,
    GSTRegistrationNotFoundException,
)
from app.modules.gst.models import GSTRegistration
from app.modules.gst.schemas import (
    GSTRegistrationCreate,
    GSTRegistrationResponse,
    GSTRegistrationUpdate,
)


class GSTRegistrationPersistence(Protocol):
    """Repository behavior required by GST registration service."""

    async def create(
        self,
        request: GSTRegistrationCreate,
        *,
        business_id: uuid.UUID,
    ) -> GSTRegistration:
        """Create registration."""
        ...

    async def update(
        self,
        registration: GSTRegistration,
        request: GSTRegistrationUpdate,
    ) -> GSTRegistration:
        """Update registration."""
        ...

    async def deactivate(self, registration: GSTRegistration) -> GSTRegistration:
        """Deactivate registration."""
        ...

    async def get_by_id(self, registration_id: uuid.UUID) -> GSTRegistration | None:
        """Return registration by UUID."""
        ...

    async def get_active_by_business(
        self,
        business_id: uuid.UUID,
    ) -> GSTRegistration | None:
        """Return active registration."""
        ...

    async def list(
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
    ) -> Page[GSTRegistration]:
        """List registrations."""
        ...


class GSTRegistrationUnitOfWork(Protocol):
    """Unit of Work contract for GST registration service."""

    gst_registrations: GSTRegistrationPersistence

    async def __aenter__(self) -> "GSTRegistrationUnitOfWork":
        """Enter transaction."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit transaction."""
        ...

    async def commit(self) -> None:
        """Commit transaction."""
        ...


UnitOfWorkFactory = Callable[[], GSTRegistrationUnitOfWork]


class GSTRegistrationService:
    """Coordinate GST registration workflows."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
    ) -> None:
        """Initialize dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher

    async def create_registration(
        self,
        request: GSTRegistrationCreate,
        *,
        business_id: uuid.UUID,
    ) -> GSTRegistrationResponse:
        """Create GST registration for a business."""
        validated = GSTRegistrationCreate.model_validate(request)
        async with self._unit_of_work_factory() as uow:
            if validated.is_active:
                active = await uow.gst_registrations.get_active_by_business(business_id)
                if active is not None:
                    raise GSTDuplicateRegistrationException(
                        "Business already has an active GST registration",
                        details={"business_id": str(business_id)},
                    )
            registration = await uow.gst_registrations.create(
                validated,
                business_id=business_id,
            )
            await self._event_dispatcher.dispatch(
                GSTRegistrationCreatedEvent(
                    registration_id=registration.id,
                    business_id=business_id,
                )
            )
            await uow.commit()
        return GSTRegistrationResponse.model_validate(registration)

    async def update_registration(
        self,
        registration_id: uuid.UUID,
        request: GSTRegistrationUpdate,
    ) -> GSTRegistrationResponse:
        """Update GST registration."""
        validated = GSTRegistrationUpdate.model_validate(request)
        async with self._unit_of_work_factory() as uow:
            registration = await self._get_registration(uow, registration_id)
            if validated.is_active is True and not registration.is_active:
                active = await uow.gst_registrations.get_active_by_business(
                    registration.business_id
                )
                if active is not None and active.id != registration_id:
                    raise GSTDuplicateRegistrationException(
                        "Business already has an active GST registration",
                        details={"business_id": str(registration.business_id)},
                    )
            registration = await uow.gst_registrations.update(
                registration,
                validated,
            )
            await self._event_dispatcher.dispatch(
                GSTRegistrationUpdatedEvent(
                    registration_id=registration.id,
                    business_id=registration.business_id,
                )
            )
            await uow.commit()
        return GSTRegistrationResponse.model_validate(registration)

    async def deactivate_registration(
        self,
        registration_id: uuid.UUID,
    ) -> GSTRegistrationResponse:
        """Deactivate GST registration."""
        async with self._unit_of_work_factory() as uow:
            registration = await self._get_registration(uow, registration_id)
            registration = await uow.gst_registrations.deactivate(registration)
            await self._event_dispatcher.dispatch(
                GSTRegistrationUpdatedEvent(
                    registration_id=registration.id,
                    business_id=registration.business_id,
                )
            )
            await uow.commit()
        return GSTRegistrationResponse.model_validate(registration)

    async def get_registration(
        self,
        registration_id: uuid.UUID,
    ) -> GSTRegistrationResponse:
        """Return GST registration."""
        async with self._unit_of_work_factory() as uow:
            registration = await self._get_registration(uow, registration_id)
            await uow.commit()
        return GSTRegistrationResponse.model_validate(registration)

    async def list_registrations(
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
    ) -> Page[GSTRegistrationResponse]:
        """List GST registrations for a business."""
        async with self._unit_of_work_factory() as uow:
            page = await uow.gst_registrations.list(
                business_id=business_id,
                pagination=pagination,
            )
            await uow.commit()
        return Page.create(
            items=[GSTRegistrationResponse.model_validate(item) for item in page.items],
            total=page.meta.total,
            params=pagination or PaginationParams(),
        )

    async def _get_registration(
        self,
        uow: GSTRegistrationUnitOfWork,
        registration_id: uuid.UUID,
    ) -> GSTRegistration:
        """Return registration or raise."""
        registration = await uow.gst_registrations.get_by_id(registration_id)
        if registration is None:
            raise GSTRegistrationNotFoundException(
                "GST registration not found",
                details={"registration_id": str(registration_id)},
            )
        return registration
