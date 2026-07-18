"""Warehouse service."""

import uuid
from collections.abc import Callable
from decimal import Decimal
from typing import Protocol

from app.common.events import EventDispatcher
from app.common.pagination import Page, PaginationParams
from app.modules.inventory.events import (
    WarehouseActivatedEvent,
    WarehouseCreatedEvent,
    WarehouseDeactivatedEvent,
    WarehouseUpdatedEvent,
)
from app.modules.inventory.exceptions import (
    ActiveStockExistsException,
    DefaultWarehouseException,
    DuplicateWarehouseException,
    WarehouseActiveException,
    WarehouseInactiveException,
    WarehouseNotFoundException,
)
from app.modules.inventory.models import StockBalance, Warehouse
from app.modules.inventory.schemas import (
    WarehouseCreate,
    WarehouseListResponse,
    WarehouseResponse,
    WarehouseUpdate,
)

ZERO_QUANTITY = Decimal("0.0000")


class WarehousePersistenceRepository(Protocol):
    """Warehouse repository behavior required by warehouse service."""

    async def create(
        self,
        request: WarehouseCreate,
        *,
        business_id: uuid.UUID,
    ) -> Warehouse:
        """Create a warehouse."""
        ...

    async def get_by_id(self, warehouse_id: uuid.UUID) -> Warehouse | None:
        """Return a warehouse by UUID."""
        ...

    async def get_by_code(
        self,
        *,
        business_id: uuid.UUID,
        code: str,
    ) -> Warehouse | None:
        """Return a warehouse by code."""
        ...

    async def list(
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        sort: str | None = None,
        code: str | None = None,
        name: str | None = None,
        is_active: bool | None = None,
    ) -> Page[Warehouse]:
        """Return warehouses for a business."""
        ...

    async def update(
        self,
        warehouse: Warehouse,
        request: WarehouseUpdate,
    ) -> Warehouse:
        """Update a warehouse."""
        ...


class WarehouseStockBalanceRepository(Protocol):
    """Stock balance repository behavior required by warehouse service."""

    async def list(
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        warehouse_id: uuid.UUID | None = None,
    ) -> Page[StockBalance]:
        """Return stock balances for a warehouse."""
        ...


class WarehouseUnitOfWork(Protocol):
    """Unit of Work contract required by warehouse service."""

    warehouses: WarehousePersistenceRepository
    stock_balances: WarehouseStockBalanceRepository

    async def __aenter__(self) -> "WarehouseUnitOfWork":
        """Enter the warehouse transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the warehouse transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit warehouse changes."""
        ...


UnitOfWorkFactory = Callable[[], WarehouseUnitOfWork]


class WarehouseService:
    """Coordinate warehouse lifecycle operations."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
    ) -> None:
        """Initialize service dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher

    async def create_warehouse(
        self,
        request: WarehouseCreate,
        *,
        business_id: uuid.UUID,
    ) -> WarehouseResponse:
        """Create a warehouse and publish an event."""
        validated_request = WarehouseCreate.model_validate(request)
        async with self._unit_of_work_factory() as uow:
            await self._ensure_unique_code(
                uow,
                business_id=business_id,
                code=validated_request.code,
            )
            if validated_request.is_default:
                await self._ensure_no_default_warehouse(uow, business_id)
            warehouse = await uow.warehouses.create(
                validated_request,
                business_id=business_id,
            )
            await self._event_dispatcher.dispatch(
                WarehouseCreatedEvent(
                    warehouse_id=warehouse.id,
                    business_id=warehouse.business_id,
                )
            )
            await uow.commit()
        return WarehouseResponse.model_validate(warehouse)

    async def update_warehouse(
        self,
        warehouse_id: uuid.UUID,
        request: WarehouseUpdate,
        *,
        business_id: uuid.UUID,
    ) -> WarehouseResponse:
        """Update a warehouse and publish an event."""
        validated_request = WarehouseUpdate.model_validate(request)
        async with self._unit_of_work_factory() as uow:
            warehouse = await self._get_existing_warehouse(
                uow,
                warehouse_id,
                business_id,
            )
            if validated_request.code is not None:
                await self._ensure_unique_code(
                    uow,
                    business_id=business_id,
                    code=validated_request.code,
                    current_warehouse_id=warehouse.id,
                )
            if validated_request.is_default is True and not warehouse.is_default:
                await self._ensure_no_default_warehouse(uow, business_id)
            warehouse = await uow.warehouses.update(warehouse, validated_request)
            await self._event_dispatcher.dispatch(
                WarehouseUpdatedEvent(
                    warehouse_id=warehouse.id,
                    business_id=warehouse.business_id,
                )
            )
            await uow.commit()
        return WarehouseResponse.model_validate(warehouse)

    async def activate_warehouse(
        self,
        warehouse_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
    ) -> WarehouseResponse:
        """Activate a warehouse and publish an event."""
        async with self._unit_of_work_factory() as uow:
            warehouse = await self._get_existing_warehouse(
                uow,
                warehouse_id,
                business_id,
            )
            if warehouse.is_active:
                raise WarehouseActiveException(
                    "Warehouse is already active",
                    details={"warehouse_id": str(warehouse_id)},
                )
            warehouse = await uow.warehouses.update(
                warehouse,
                WarehouseUpdate(is_active=True),
            )
            await self._event_dispatcher.dispatch(
                WarehouseActivatedEvent(
                    warehouse_id=warehouse.id,
                    business_id=warehouse.business_id,
                )
            )
            await uow.commit()
        return WarehouseResponse.model_validate(warehouse)

    async def deactivate_warehouse(
        self,
        warehouse_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
    ) -> WarehouseResponse:
        """Deactivate a non-default warehouse with no active stock."""
        async with self._unit_of_work_factory() as uow:
            warehouse = await self._get_existing_warehouse(
                uow,
                warehouse_id,
                business_id,
            )
            if not warehouse.is_active:
                raise WarehouseInactiveException(
                    "Warehouse is already inactive",
                    details={"warehouse_id": str(warehouse_id)},
                )
            if warehouse.is_default:
                raise DefaultWarehouseException(
                    "Default warehouse cannot be deactivated",
                    details={"warehouse_id": str(warehouse_id)},
                )
            await self._ensure_no_active_stock(uow, warehouse)
            warehouse = await uow.warehouses.update(
                warehouse,
                WarehouseUpdate(is_active=False),
            )
            await self._event_dispatcher.dispatch(
                WarehouseDeactivatedEvent(
                    warehouse_id=warehouse.id,
                    business_id=warehouse.business_id,
                )
            )
            await uow.commit()
        return WarehouseResponse.model_validate(warehouse)

    async def get_warehouse(
        self,
        warehouse_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
    ) -> WarehouseResponse:
        """Return a warehouse by UUID within a business."""
        async with self._unit_of_work_factory() as uow:
            warehouse = await self._get_existing_warehouse(
                uow,
                warehouse_id,
                business_id,
            )
            await uow.commit()
        return WarehouseResponse.model_validate(warehouse)

    async def list_warehouses(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        sort: str | None = None,
        code: str | None = None,
        name: str | None = None,
        is_active: bool | None = None,
    ) -> Page[WarehouseListResponse]:
        """Return paginated warehouses for a business."""
        async with self._unit_of_work_factory() as uow:
            page = await uow.warehouses.list(
                business_id=business_id,
                pagination=pagination,
                sort=sort,
                code=code,
                name=name,
                is_active=is_active,
            )
            await uow.commit()
        return Page.create(
            items=[
                WarehouseListResponse.model_validate(warehouse)
                for warehouse in page.items
            ],
            total=page.meta.total,
            params=pagination or PaginationParams(),
        )

    async def _get_existing_warehouse(
        self,
        uow: WarehouseUnitOfWork,
        warehouse_id: uuid.UUID,
        business_id: uuid.UUID,
    ) -> Warehouse:
        """Return a warehouse or raise not found."""
        warehouse = await uow.warehouses.get_by_id(warehouse_id)
        if warehouse is None or warehouse.business_id != business_id:
            raise WarehouseNotFoundException(
                "Warehouse not found",
                details={"warehouse_id": str(warehouse_id)},
            )
        return warehouse

    async def _ensure_unique_code(
        self,
        uow: WarehouseUnitOfWork,
        *,
        business_id: uuid.UUID,
        code: str,
        current_warehouse_id: uuid.UUID | None = None,
    ) -> None:
        """Validate warehouse code uniqueness within a business."""
        existing = await uow.warehouses.get_by_code(
            business_id=business_id,
            code=code,
        )
        if existing is not None and existing.id != current_warehouse_id:
            raise DuplicateWarehouseException(
                "Warehouse code already exists for this business",
                details={"business_id": str(business_id), "code": code},
            )

    async def _ensure_no_default_warehouse(
        self,
        uow: WarehouseUnitOfWork,
        business_id: uuid.UUID,
    ) -> None:
        """Raise when a business already has a default warehouse."""
        page = await uow.warehouses.list(
            business_id=business_id,
            pagination=PaginationParams(page=1, size=100),
        )
        if any(warehouse.is_default for warehouse in page.items):
            raise DefaultWarehouseException(
                "Only one default warehouse is allowed per business",
                details={"business_id": str(business_id)},
            )

    async def _ensure_no_active_stock(
        self,
        uow: WarehouseUnitOfWork,
        warehouse: Warehouse,
    ) -> None:
        """Raise when warehouse has stock on hand."""
        page = await uow.stock_balances.list(
            business_id=warehouse.business_id,
            warehouse_id=warehouse.id,
            pagination=PaginationParams(page=1, size=100),
        )
        if any(balance.quantity_on_hand > ZERO_QUANTITY for balance in page.items):
            raise ActiveStockExistsException(
                "Warehouse cannot be deactivated while stock exists",
                details={"warehouse_id": str(warehouse.id)},
            )
