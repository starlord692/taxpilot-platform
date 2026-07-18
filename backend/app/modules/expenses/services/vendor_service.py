"""Vendor service."""

import uuid
from collections.abc import Callable
from typing import Protocol

from app.common.events import EventDispatcher
from app.common.pagination import Page, PaginationParams
from app.modules.expenses.events import (
    VendorCreatedEvent,
    VendorDeactivatedEvent,
    VendorUpdatedEvent,
)
from app.modules.expenses.exceptions import (
    DuplicateVendorCodeException,
    VendorInactiveException,
    VendorNotFoundException,
)
from app.modules.expenses.models import Vendor
from app.modules.expenses.schemas import (
    VendorCreate,
    VendorListResponse,
    VendorResponse,
    VendorUpdate,
)


class VendorPersistenceRepository(Protocol):
    """Vendor repository behavior required by vendor service."""

    async def create(
        self,
        request: VendorCreate,
        *,
        business_id: uuid.UUID,
        vendor_code: str,
    ) -> Vendor:
        """Create a vendor."""
        ...

    async def get_by_id(self, vendor_id: uuid.UUID) -> Vendor | None:
        """Return a vendor by UUID."""
        ...

    async def get_by_vendor_code(
        self,
        *,
        business_id: uuid.UUID,
        vendor_code: str,
    ) -> Vendor | None:
        """Return a vendor by code."""
        ...

    async def list_by_business(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        sort: str | None = None,
    ) -> Page[Vendor]:
        """Return vendors for a business."""
        ...

    async def update(self, vendor: Vendor, request: VendorUpdate) -> Vendor:
        """Update a vendor."""
        ...

    async def delete(self, vendor: Vendor) -> None:
        """Soft-delete a vendor."""
        ...


class VendorUnitOfWork(Protocol):
    """Unit of Work contract required by vendor service."""

    vendors: VendorPersistenceRepository

    async def __aenter__(self) -> "VendorUnitOfWork":
        """Enter the vendor transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the vendor transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit vendor changes."""
        ...


UnitOfWorkFactory = Callable[[], VendorUnitOfWork]


class VendorService:
    """Coordinate vendor lifecycle operations."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
    ) -> None:
        """Initialize service dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher

    async def create_vendor(
        self,
        request: VendorCreate,
        *,
        business_id: uuid.UUID,
    ) -> VendorResponse:
        """Create a vendor, generate a vendor code, and publish an event."""
        validated_request = VendorCreate.model_validate(request)
        async with self._unit_of_work_factory() as uow:
            vendor_code = await self._generate_unique_vendor_code(uow, business_id)
            vendor = await uow.vendors.create(
                validated_request,
                business_id=business_id,
                vendor_code=vendor_code,
            )
            await self._event_dispatcher.dispatch(
                VendorCreatedEvent(vendor_id=vendor.id, business_id=vendor.business_id)
            )
            await uow.commit()
        return VendorResponse.model_validate(vendor)

    async def update_vendor(
        self,
        vendor_id: uuid.UUID,
        request: VendorUpdate,
    ) -> VendorResponse:
        """Update a vendor and publish an event."""
        validated_request = VendorUpdate.model_validate(request)
        async with self._unit_of_work_factory() as uow:
            vendor = await self._get_existing_vendor(uow, vendor_id)
            vendor = await uow.vendors.update(vendor, validated_request)
            await self._event_dispatcher.dispatch(
                VendorUpdatedEvent(vendor_id=vendor.id, business_id=vendor.business_id)
            )
            await uow.commit()
        return VendorResponse.model_validate(vendor)

    async def deactivate_vendor(self, vendor_id: uuid.UUID) -> VendorResponse:
        """Deactivate a vendor and publish an event."""
        async with self._unit_of_work_factory() as uow:
            vendor = await self._get_existing_vendor(uow, vendor_id)
            if not vendor.is_active:
                raise VendorInactiveException(
                    "Vendor is already inactive",
                    details={"vendor_id": str(vendor_id)},
                )
            vendor = await uow.vendors.update(
                vendor,
                VendorUpdate(is_active=False),
            )
            await self._event_dispatcher.dispatch(
                VendorDeactivatedEvent(
                    vendor_id=vendor.id,
                    business_id=vendor.business_id,
                )
            )
            await uow.commit()
        return VendorResponse.model_validate(vendor)

    async def get_vendor(self, vendor_id: uuid.UUID) -> VendorResponse:
        """Return a vendor by UUID."""
        async with self._unit_of_work_factory() as uow:
            vendor = await self._get_existing_vendor(uow, vendor_id)
            await uow.commit()
        return VendorResponse.model_validate(vendor)

    async def list_vendors(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        sort: str | None = None,
    ) -> Page[VendorListResponse]:
        """Return paginated vendors for a business."""
        async with self._unit_of_work_factory() as uow:
            page = await uow.vendors.list_by_business(
                business_id,
                pagination,
                sort=sort,
            )
            await uow.commit()
        return Page.create(
            items=[VendorListResponse.model_validate(vendor) for vendor in page.items],
            total=page.meta.total,
            params=pagination or PaginationParams(),
        )

    async def _get_existing_vendor(
        self,
        uow: VendorUnitOfWork,
        vendor_id: uuid.UUID,
    ) -> Vendor:
        """Return a vendor or raise not found."""
        vendor = await uow.vendors.get_by_id(vendor_id)
        if vendor is None:
            raise VendorNotFoundException(
                "Vendor not found",
                details={"vendor_id": str(vendor_id)},
            )
        return vendor

    async def _generate_unique_vendor_code(
        self,
        uow: VendorUnitOfWork,
        business_id: uuid.UUID,
    ) -> str:
        """Generate a unique business-scoped vendor code."""
        for _attempt in range(10):
            vendor_code = f"VEND-{uuid.uuid4().hex[:8].upper()}"
            existing = await uow.vendors.get_by_vendor_code(
                business_id=business_id,
                vendor_code=vendor_code,
            )
            if existing is None:
                return vendor_code
        raise DuplicateVendorCodeException(
            "Unable to generate a unique vendor code",
            details={"business_id": str(business_id)},
        )
