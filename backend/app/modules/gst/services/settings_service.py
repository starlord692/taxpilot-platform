"""GST settings service."""

import uuid
from collections.abc import Callable
from typing import Protocol

from app.common.events import EventDispatcher
from app.modules.gst.events import GSTSettingsChangedEvent
from app.modules.gst.exceptions import (
    GSTDuplicateSettingsException,
    GSTSettingsNotFoundException,
)
from app.modules.gst.models import GSTSettings
from app.modules.gst.schemas import (
    GSTSettingsCreate,
    GSTSettingsResponse,
    GSTSettingsUpdate,
)


class GSTSettingsPersistence(Protocol):
    """Repository behavior required by settings service."""

    async def create(
        self,
        request: GSTSettingsCreate,
        *,
        business_id: uuid.UUID,
    ) -> GSTSettings:
        """Create settings."""
        ...

    async def update(
        self,
        settings: GSTSettings,
        request: GSTSettingsUpdate,
    ) -> GSTSettings:
        """Update settings."""
        ...

    async def get_by_business(self, business_id: uuid.UUID) -> GSTSettings | None:
        """Return settings by business."""
        ...

    async def get_by_id(self, settings_id: uuid.UUID) -> GSTSettings | None:
        """Return settings by UUID."""
        ...


class GSTSettingsUnitOfWork(Protocol):
    """Unit of Work contract for GST settings service."""

    gst_settings: GSTSettingsPersistence

    async def __aenter__(self) -> "GSTSettingsUnitOfWork":
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


UnitOfWorkFactory = Callable[[], GSTSettingsUnitOfWork]


class GSTSettingsService:
    """Coordinate GST settings workflows."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
    ) -> None:
        """Initialize dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher

    async def create_settings(
        self,
        request: GSTSettingsCreate,
        *,
        business_id: uuid.UUID,
    ) -> GSTSettingsResponse:
        """Create GST settings."""
        validated = GSTSettingsCreate.model_validate(request)
        async with self._unit_of_work_factory() as uow:
            existing = await uow.gst_settings.get_by_business(business_id)
            if existing is not None:
                raise GSTDuplicateSettingsException(
                    "GST settings already exist for this business",
                    details={"business_id": str(business_id)},
                )
            settings = await uow.gst_settings.create(
                validated,
                business_id=business_id,
            )
            await self._event_dispatcher.dispatch(
                GSTSettingsChangedEvent(
                    settings_id=settings.id,
                    business_id=settings.business_id,
                )
            )
            await uow.commit()
        return GSTSettingsResponse.model_validate(settings)

    async def update_settings(
        self,
        business_id: uuid.UUID,
        request: GSTSettingsUpdate,
    ) -> GSTSettingsResponse:
        """Update GST settings."""
        validated = GSTSettingsUpdate.model_validate(request)
        async with self._unit_of_work_factory() as uow:
            settings = await self._get_settings(uow, business_id)
            settings = await uow.gst_settings.update(settings, validated)
            await self._event_dispatcher.dispatch(
                GSTSettingsChangedEvent(
                    settings_id=settings.id,
                    business_id=settings.business_id,
                )
            )
            await uow.commit()
        return GSTSettingsResponse.model_validate(settings)

    async def get_settings(self, business_id: uuid.UUID) -> GSTSettingsResponse:
        """Return GST settings."""
        async with self._unit_of_work_factory() as uow:
            settings = await self._get_settings(uow, business_id)
            await uow.commit()
        return GSTSettingsResponse.model_validate(settings)

    async def deactivate_settings(self, business_id: uuid.UUID) -> GSTSettingsResponse:
        """Disable manual override without deleting settings."""
        return await self.update_settings(
            business_id,
            GSTSettingsUpdate(allow_manual_override=False),
        )

    async def _get_settings(
        self,
        uow: GSTSettingsUnitOfWork,
        business_id: uuid.UUID,
    ) -> GSTSettings:
        """Return settings or raise."""
        settings = await uow.gst_settings.get_by_business(business_id)
        if settings is None:
            raise GSTSettingsNotFoundException(
                "GST settings not found",
                details={"business_id": str(business_id)},
            )
        return settings
