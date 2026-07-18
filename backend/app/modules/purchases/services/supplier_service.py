"""Supplier service."""

import uuid
from collections.abc import Callable
from typing import Protocol

from app.common.events import EventDispatcher
from app.common.pagination import Page, PaginationParams
from app.modules.purchases.events import (
    SupplierCreatedEvent,
    SupplierDeactivatedEvent,
    SupplierReactivatedEvent,
    SupplierUpdatedEvent,
)
from app.modules.purchases.exceptions import (
    DuplicateSupplierCodeException,
    DuplicateSupplierException,
    SupplierHasOpenPurchasesException,
    SupplierInactiveException,
    SupplierNotFoundException,
)
from app.modules.purchases.models import PurchaseInvoice, PurchaseStatus, Supplier
from app.modules.purchases.schemas import (
    SupplierCreate,
    SupplierListResponse,
    SupplierResponse,
    SupplierUpdate,
)

SUPPLIER_CODE_ATTEMPTS = 10
OPEN_PURCHASE_STATUSES = (
    PurchaseStatus.DRAFT,
    PurchaseStatus.APPROVED,
    PurchaseStatus.RECEIVED,
)


class SupplierPersistenceRepository(Protocol):
    """Supplier repository behavior required by supplier service."""

    async def create(
        self,
        request: SupplierCreate,
        *,
        business_id: uuid.UUID,
        supplier_code: str,
    ) -> Supplier:
        """Create a supplier."""
        ...

    async def get_by_id(self, supplier_id: uuid.UUID) -> Supplier | None:
        """Return a supplier by UUID."""
        ...

    async def get_by_supplier_code(
        self,
        *,
        business_id: uuid.UUID,
        supplier_code: str,
    ) -> Supplier | None:
        """Return a supplier by code."""
        ...

    async def get_by_gstin(
        self,
        *,
        business_id: uuid.UUID,
        gstin: str,
    ) -> Supplier | None:
        """Return a supplier by GSTIN."""
        ...

    async def list(
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        sort: str | None = None,
    ) -> Page[Supplier]:
        """Return suppliers for a business."""
        ...

    async def search(
        self,
        *,
        business_id: uuid.UUID,
        query: str,
        pagination: PaginationParams | None = None,
    ) -> Page[Supplier]:
        """Search suppliers for a business."""
        ...

    async def update(self, supplier: Supplier, request: SupplierUpdate) -> Supplier:
        """Update a supplier."""
        ...


class SupplierPurchaseRepository(Protocol):
    """Purchase repository behavior required by supplier service."""

    async def list(
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        supplier_id: uuid.UUID | None = None,
        status: PurchaseStatus | None = None,
    ) -> Page[PurchaseInvoice]:
        """Return purchases for a supplier."""
        ...


class SupplierUnitOfWork(Protocol):
    """Unit of Work contract required by supplier service."""

    suppliers: SupplierPersistenceRepository
    purchase_invoices: SupplierPurchaseRepository

    async def __aenter__(self) -> "SupplierUnitOfWork":
        """Enter the supplier transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the supplier transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit supplier changes."""
        ...


UnitOfWorkFactory = Callable[[], SupplierUnitOfWork]


class SupplierService:
    """Coordinate supplier lifecycle operations."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
    ) -> None:
        """Initialize service dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher

    async def create_supplier(
        self,
        request: SupplierCreate,
        *,
        business_id: uuid.UUID,
    ) -> SupplierResponse:
        """Create a supplier, generate a code, and publish an event."""
        validated_request = SupplierCreate.model_validate(request)
        async with self._unit_of_work_factory() as uow:
            await self._ensure_unique_supplier(
                uow,
                business_id=business_id,
                request=validated_request,
            )
            supplier_code = await self._generate_unique_supplier_code(
                uow,
                business_id,
            )
            supplier = await uow.suppliers.create(
                validated_request,
                business_id=business_id,
                supplier_code=supplier_code,
            )
            await self._event_dispatcher.dispatch(
                SupplierCreatedEvent(
                    supplier_id=supplier.id,
                    business_id=supplier.business_id,
                )
            )
            await uow.commit()
        return SupplierResponse.model_validate(supplier)

    async def update_supplier(
        self,
        supplier_id: uuid.UUID,
        request: SupplierUpdate,
    ) -> SupplierResponse:
        """Update a supplier and publish an event."""
        validated_request = SupplierUpdate.model_validate(request)
        async with self._unit_of_work_factory() as uow:
            supplier = await self._get_existing_supplier(uow, supplier_id)
            await self._ensure_unique_supplier(
                uow,
                business_id=supplier.business_id,
                request=validated_request,
                current_supplier_id=supplier.id,
            )
            supplier = await uow.suppliers.update(supplier, validated_request)
            await self._event_dispatcher.dispatch(
                SupplierUpdatedEvent(
                    supplier_id=supplier.id,
                    business_id=supplier.business_id,
                )
            )
            await uow.commit()
        return SupplierResponse.model_validate(supplier)

    async def deactivate_supplier(self, supplier_id: uuid.UUID) -> SupplierResponse:
        """Deactivate a supplier when no unpaid purchases remain."""
        async with self._unit_of_work_factory() as uow:
            supplier = await self._get_existing_supplier(uow, supplier_id)
            if not supplier.is_active:
                raise SupplierInactiveException(
                    "Supplier is already inactive",
                    details={"supplier_id": str(supplier_id)},
                )
            await self._ensure_no_open_purchases(uow, supplier)
            supplier = await uow.suppliers.update(
                supplier,
                SupplierUpdate(is_active=False),
            )
            await self._event_dispatcher.dispatch(
                SupplierDeactivatedEvent(
                    supplier_id=supplier.id,
                    business_id=supplier.business_id,
                )
            )
            await uow.commit()
        return SupplierResponse.model_validate(supplier)

    async def reactivate_supplier(self, supplier_id: uuid.UUID) -> SupplierResponse:
        """Reactivate an inactive supplier and publish an event."""
        async with self._unit_of_work_factory() as uow:
            supplier = await self._get_existing_supplier(uow, supplier_id)
            supplier = await uow.suppliers.update(
                supplier,
                SupplierUpdate(is_active=True),
            )
            await self._event_dispatcher.dispatch(
                SupplierReactivatedEvent(
                    supplier_id=supplier.id,
                    business_id=supplier.business_id,
                )
            )
            await uow.commit()
        return SupplierResponse.model_validate(supplier)

    async def get_supplier(self, supplier_id: uuid.UUID) -> SupplierResponse:
        """Return a supplier by UUID."""
        async with self._unit_of_work_factory() as uow:
            supplier = await self._get_existing_supplier(uow, supplier_id)
            await uow.commit()
        return SupplierResponse.model_validate(supplier)

    async def list_suppliers(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        sort: str | None = None,
        search: str | None = None,
    ) -> Page[SupplierListResponse]:
        """Return paginated suppliers for a business."""
        async with self._unit_of_work_factory() as uow:
            if search:
                page = await uow.suppliers.search(
                    business_id=business_id,
                    query=search,
                    pagination=pagination,
                )
            else:
                page = await uow.suppliers.list(
                    business_id=business_id,
                    pagination=pagination,
                    sort=sort,
                )
            await uow.commit()
        return Page.create(
            items=[
                SupplierListResponse.model_validate(supplier)
                for supplier in page.items
            ],
            total=page.meta.total,
            params=pagination or PaginationParams(),
        )

    async def _get_existing_supplier(
        self,
        uow: SupplierUnitOfWork,
        supplier_id: uuid.UUID,
    ) -> Supplier:
        """Return a supplier or raise not found."""
        supplier = await uow.suppliers.get_by_id(supplier_id)
        if supplier is None:
            raise SupplierNotFoundException(
                "Supplier not found",
                details={"supplier_id": str(supplier_id)},
            )
        return supplier

    async def _ensure_unique_supplier(
        self,
        uow: SupplierUnitOfWork,
        *,
        business_id: uuid.UUID,
        request: SupplierCreate | SupplierUpdate,
        current_supplier_id: uuid.UUID | None = None,
    ) -> None:
        """Validate supplier name and GSTIN uniqueness within a business."""
        if request.name is not None:
            page = await uow.suppliers.search(
                business_id=business_id,
                query=request.name,
                pagination=PaginationParams(page=1, size=100),
            )
            normalized_name = request.name.casefold()
            if any(
                supplier.name.casefold() == normalized_name
                and supplier.id != current_supplier_id
                for supplier in page.items
            ):
                raise DuplicateSupplierException(
                    "Supplier name already exists for this business",
                    details={"business_id": str(business_id), "name": request.name},
                )

        if request.gstin is not None:
            existing = await uow.suppliers.get_by_gstin(
                business_id=business_id,
                gstin=request.gstin,
            )
            if existing is not None and existing.id != current_supplier_id:
                raise DuplicateSupplierException(
                    "Supplier GSTIN already exists for this business",
                    details={"business_id": str(business_id), "gstin": request.gstin},
                )

    async def _ensure_no_open_purchases(
        self,
        uow: SupplierUnitOfWork,
        supplier: Supplier,
    ) -> None:
        """Raise when supplier has active unpaid purchase invoices."""
        for status in OPEN_PURCHASE_STATUSES:
            page = await uow.purchase_invoices.list(
                business_id=supplier.business_id,
                supplier_id=supplier.id,
                status=status,
                pagination=PaginationParams(page=1, size=1),
            )
            if page.meta.total > 0:
                raise SupplierHasOpenPurchasesException(
                    "Supplier cannot be deactivated with unpaid purchase invoices",
                    details={
                        "supplier_id": str(supplier.id),
                        "status": status.value,
                    },
                )

    async def _generate_unique_supplier_code(
        self,
        uow: SupplierUnitOfWork,
        business_id: uuid.UUID,
    ) -> str:
        """Generate a unique business-scoped supplier code."""
        for _attempt in range(SUPPLIER_CODE_ATTEMPTS):
            supplier_code = f"SUP-{uuid.uuid4().hex[:8].upper()}"
            existing = await uow.suppliers.get_by_supplier_code(
                business_id=business_id,
                supplier_code=supplier_code,
            )
            if existing is None:
                return supplier_code
        raise DuplicateSupplierCodeException(
            "Unable to generate a unique supplier code",
            details={"business_id": str(business_id)},
        )
