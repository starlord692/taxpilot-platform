"""Inventory API dependencies."""

from collections.abc import Callable
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.events import EventDispatcher
from app.common.unit_of_work import SQLAlchemyUnitOfWork
from app.core.database import database_state, initialize_database
from app.modules.inventory.services import (
    InventoryService,
    ProductService,
    WarehouseService,
)
from app.modules.inventory.services.inventory_service import InventoryUnitOfWork
from app.modules.inventory.services.product_service import ProductUnitOfWork
from app.modules.inventory.services.warehouse_service import WarehouseUnitOfWork


def get_session_factory() -> Callable[[], AsyncSession]:
    """Return the configured async session factory."""
    if database_state.session_factory is None:
        initialize_database()

    if database_state.session_factory is None:
        raise RuntimeError("Database session factory is not initialized")

    return database_state.session_factory


def get_event_dispatcher() -> EventDispatcher:
    """Provide an event dispatcher instance."""
    return EventDispatcher()


def get_inventory_unit_of_work() -> InventoryUnitOfWork:
    """Provide an Inventory Unit of Work."""
    session_factory = get_session_factory()
    return cast(InventoryUnitOfWork, SQLAlchemyUnitOfWork(session_factory))


def get_product_service() -> ProductService:
    """Provide the product service with injected dependencies."""
    session_factory = get_session_factory()
    unit_of_work_factory = cast(
        Callable[[], ProductUnitOfWork],
        lambda: SQLAlchemyUnitOfWork(session_factory),
    )
    return ProductService(
        unit_of_work_factory=unit_of_work_factory,
        event_dispatcher=get_event_dispatcher(),
    )


def get_warehouse_service() -> WarehouseService:
    """Provide the warehouse service with injected dependencies."""
    session_factory = get_session_factory()
    unit_of_work_factory = cast(
        Callable[[], WarehouseUnitOfWork],
        lambda: SQLAlchemyUnitOfWork(session_factory),
    )
    return WarehouseService(
        unit_of_work_factory=unit_of_work_factory,
        event_dispatcher=get_event_dispatcher(),
    )


def get_inventory_service() -> InventoryService:
    """Provide the inventory read service with injected dependencies."""
    session_factory = get_session_factory()
    unit_of_work_factory = cast(
        Callable[[], InventoryUnitOfWork],
        lambda: SQLAlchemyUnitOfWork(session_factory),
    )
    return InventoryService(unit_of_work_factory=unit_of_work_factory)
