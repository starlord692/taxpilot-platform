"""Purchase API dependencies."""

from collections.abc import Callable
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.events import EventDispatcher
from app.common.unit_of_work import SQLAlchemyUnitOfWork
from app.core.database import database_state, initialize_database
from app.modules.accounting.kernel import AccountingKernelService
from app.modules.accounting.kernel.accounting_kernel import AccountingKernelUnitOfWork
from app.modules.purchases.services import PurchaseService, SupplierService
from app.modules.purchases.services.purchase_service import PurchaseUnitOfWork
from app.modules.purchases.services.supplier_service import SupplierUnitOfWork


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


def get_purchase_unit_of_work() -> PurchaseUnitOfWork:
    """Provide a Purchase Unit of Work."""
    session_factory = get_session_factory()
    return cast(PurchaseUnitOfWork, SQLAlchemyUnitOfWork(session_factory))


def get_supplier_service() -> SupplierService:
    """Provide the supplier service with injected dependencies."""
    session_factory = get_session_factory()
    unit_of_work_factory = cast(
        Callable[[], SupplierUnitOfWork],
        lambda: SQLAlchemyUnitOfWork(session_factory),
    )
    return SupplierService(
        unit_of_work_factory=unit_of_work_factory,
        event_dispatcher=get_event_dispatcher(),
    )


def get_accounting_kernel_service() -> AccountingKernelService:
    """Provide the accounting kernel service with injected dependencies."""
    session_factory = get_session_factory()
    unit_of_work_factory = cast(
        Callable[[], AccountingKernelUnitOfWork],
        lambda: SQLAlchemyUnitOfWork(session_factory),
    )
    return AccountingKernelService(
        unit_of_work_factory=unit_of_work_factory,
        event_dispatcher=get_event_dispatcher(),
    )


def get_purchase_service() -> PurchaseService:
    """Provide the purchase service with injected dependencies."""
    session_factory = get_session_factory()
    unit_of_work_factory = cast(
        Callable[[], PurchaseUnitOfWork],
        lambda: SQLAlchemyUnitOfWork(session_factory),
    )
    return PurchaseService(
        unit_of_work_factory=unit_of_work_factory,
        event_dispatcher=get_event_dispatcher(),
        accounting_kernel=get_accounting_kernel_service(),
    )
