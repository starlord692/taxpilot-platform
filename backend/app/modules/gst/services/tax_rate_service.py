"""GST tax rate service."""

import uuid
from collections.abc import Callable
from typing import Protocol

from app.common.events import EventDispatcher
from app.common.pagination import Page, PaginationParams
from app.modules.gst.events import GSTTaxRateChangedEvent
from app.modules.gst.exceptions import (
    GSTDuplicateTaxRateException,
    GSTTaxRateNotFoundException,
)
from app.modules.gst.models import GSTTaxRate
from app.modules.gst.schemas import (
    GSTTaxRateCreate,
    GSTTaxRateResponse,
    GSTTaxRateUpdate,
)


class GSTTaxRatePersistence(Protocol):
    """Repository behavior required by tax rate service."""

    async def create(self, request: GSTTaxRateCreate) -> GSTTaxRate:
        """Create tax rate."""
        ...

    async def update(
        self,
        tax_rate: GSTTaxRate,
        request: GSTTaxRateUpdate,
    ) -> GSTTaxRate:
        """Update tax rate."""
        ...

    async def deactivate(self, tax_rate: GSTTaxRate) -> GSTTaxRate:
        """Deactivate tax rate."""
        ...

    async def get_by_id(self, tax_rate_id: uuid.UUID) -> GSTTaxRate | None:
        """Return tax rate by UUID."""
        ...

    async def get_by_name(self, name: str) -> GSTTaxRate | None:
        """Return tax rate by name."""
        ...

    async def list(
        self,
        *,
        pagination: PaginationParams | None = None,
        active_only: bool = False,
    ) -> Page[GSTTaxRate]:
        """List tax rates."""
        ...


class GSTTaxRateUnitOfWork(Protocol):
    """Unit of Work contract for GST tax rate service."""

    gst_tax_rates: GSTTaxRatePersistence

    async def __aenter__(self) -> "GSTTaxRateUnitOfWork":
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


UnitOfWorkFactory = Callable[[], GSTTaxRateUnitOfWork]


class GSTTaxRateService:
    """Coordinate GST tax rate workflows."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
    ) -> None:
        """Initialize dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher

    async def create_tax_rate(self, request: GSTTaxRateCreate) -> GSTTaxRateResponse:
        """Create GST tax rate."""
        validated = GSTTaxRateCreate.model_validate(request)
        async with self._unit_of_work_factory() as uow:
            duplicate = await uow.gst_tax_rates.get_by_name(validated.name)
            if duplicate is not None:
                raise GSTDuplicateTaxRateException("GST tax rate already exists")
            tax_rate = await uow.gst_tax_rates.create(validated)
            await self._event_dispatcher.dispatch(
                GSTTaxRateChangedEvent(tax_rate_id=tax_rate.id)
            )
            await uow.commit()
        return GSTTaxRateResponse.model_validate(tax_rate)

    async def update_tax_rate(
        self,
        tax_rate_id: uuid.UUID,
        request: GSTTaxRateUpdate,
    ) -> GSTTaxRateResponse:
        """Update GST tax rate."""
        validated = GSTTaxRateUpdate.model_validate(request)
        async with self._unit_of_work_factory() as uow:
            tax_rate = await self._get_tax_rate(uow, tax_rate_id)
            if validated.name is not None and validated.name != tax_rate.name:
                duplicate = await uow.gst_tax_rates.get_by_name(validated.name)
                if duplicate is not None:
                    raise GSTDuplicateTaxRateException("GST tax rate already exists")
            tax_rate = await uow.gst_tax_rates.update(tax_rate, validated)
            await self._event_dispatcher.dispatch(
                GSTTaxRateChangedEvent(tax_rate_id=tax_rate.id)
            )
            await uow.commit()
        return GSTTaxRateResponse.model_validate(tax_rate)

    async def deactivate_tax_rate(self, tax_rate_id: uuid.UUID) -> GSTTaxRateResponse:
        """Deactivate GST tax rate."""
        async with self._unit_of_work_factory() as uow:
            tax_rate = await self._get_tax_rate(uow, tax_rate_id)
            tax_rate = await uow.gst_tax_rates.deactivate(tax_rate)
            await self._event_dispatcher.dispatch(
                GSTTaxRateChangedEvent(tax_rate_id=tax_rate.id)
            )
            await uow.commit()
        return GSTTaxRateResponse.model_validate(tax_rate)

    async def get_tax_rate(self, tax_rate_id: uuid.UUID) -> GSTTaxRateResponse:
        """Return GST tax rate."""
        async with self._unit_of_work_factory() as uow:
            tax_rate = await self._get_tax_rate(uow, tax_rate_id)
            await uow.commit()
        return GSTTaxRateResponse.model_validate(tax_rate)

    async def list_tax_rates(
        self,
        pagination: PaginationParams | None = None,
        *,
        active_only: bool = False,
    ) -> Page[GSTTaxRateResponse]:
        """List GST tax rates."""
        async with self._unit_of_work_factory() as uow:
            page = await uow.gst_tax_rates.list(
                pagination=pagination,
                active_only=active_only,
            )
            await uow.commit()
        return Page.create(
            items=[GSTTaxRateResponse.model_validate(item) for item in page.items],
            total=page.meta.total,
            params=pagination or PaginationParams(),
        )

    async def _get_tax_rate(
        self,
        uow: GSTTaxRateUnitOfWork,
        tax_rate_id: uuid.UUID,
    ) -> GSTTaxRate:
        """Return tax rate or raise."""
        tax_rate = await uow.gst_tax_rates.get_by_id(tax_rate_id)
        if tax_rate is None:
            raise GSTTaxRateNotFoundException(
                "GST tax rate not found",
                details={"tax_rate_id": str(tax_rate_id)},
            )
        return tax_rate
