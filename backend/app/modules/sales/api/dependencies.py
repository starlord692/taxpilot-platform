"""Sales API dependencies."""

from collections.abc import Callable
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.events import EventDispatcher
from app.common.unit_of_work import SQLAlchemyUnitOfWork
from app.core.database import database_state, initialize_database
from app.modules.accounting.kernel import AccountingKernelService
from app.modules.accounting.kernel.accounting_kernel import AccountingKernelUnitOfWork
from app.modules.gst.api.dependencies import get_gst_calculation_service
from app.modules.inventory.services import StockEngine
from app.modules.inventory.services.stock_engine import StockEngineUnitOfWork
from app.modules.sales.canonical_service import (
    CanonicalSalesInvoiceService,
    CanonicalSalesUnitOfWork,
)
from app.modules.sales.services import PaymentService, SalesInvoiceService
from app.modules.sales.services.invoice_service import SalesInvoiceUnitOfWork
from app.modules.sales.services.payment_service import PaymentUnitOfWork


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


def get_sales_unit_of_work() -> SalesInvoiceUnitOfWork:
    """Provide a Sales Unit of Work."""
    session_factory = get_session_factory()
    return cast(SalesInvoiceUnitOfWork, SQLAlchemyUnitOfWork(session_factory))


def get_accounting_kernel_service() -> AccountingKernelService:
    """Provide the Accounting Kernel service with injected dependencies."""
    session_factory = get_session_factory()
    unit_of_work_factory = cast(
        Callable[[], AccountingKernelUnitOfWork],
        lambda: SQLAlchemyUnitOfWork(session_factory),
    )
    return AccountingKernelService(
        unit_of_work_factory=unit_of_work_factory,
        event_dispatcher=get_event_dispatcher(),
    )


def get_stock_engine() -> StockEngine:
    """Provide the Inventory Stock Movement Engine."""
    session_factory = get_session_factory()
    unit_of_work_factory = cast(
        Callable[[], StockEngineUnitOfWork],
        lambda: SQLAlchemyUnitOfWork(session_factory),
    )
    return StockEngine(
        unit_of_work_factory=unit_of_work_factory,
        event_dispatcher=get_event_dispatcher(),
    )


def get_sales_invoice_service() -> SalesInvoiceService:
    """Provide the Sales invoice service with injected dependencies."""
    session_factory = get_session_factory()
    unit_of_work_factory = cast(
        Callable[[], SalesInvoiceUnitOfWork],
        lambda: SQLAlchemyUnitOfWork(session_factory),
    )
    return SalesInvoiceService(
        unit_of_work_factory=unit_of_work_factory,
        event_dispatcher=get_event_dispatcher(),
        accounting_kernel=get_accounting_kernel_service(),
        stock_engine=get_stock_engine(),
        gst_calculation_service=get_gst_calculation_service(),
    )


def get_payment_service() -> PaymentService:
    """Provide the payment service with injected dependencies."""
    session_factory = get_session_factory()
    unit_of_work_factory = cast(
        Callable[[], PaymentUnitOfWork],
        lambda: SQLAlchemyUnitOfWork(session_factory),
    )
    return PaymentService(
        unit_of_work_factory=unit_of_work_factory,
        event_dispatcher=get_event_dispatcher(),
        accounting_kernel=get_accounting_kernel_service(),
    )


def get_canonical_sales_invoice_service() -> CanonicalSalesInvoiceService:
    """Provide the side-effect-free canonical Sales workflow."""
    session_factory = get_session_factory()
    unit_of_work_factory = cast(
        Callable[[], CanonicalSalesUnitOfWork],
        lambda: SQLAlchemyUnitOfWork(session_factory),
    )
    return CanonicalSalesInvoiceService(
        unit_of_work_factory,
        get_event_dispatcher(),
    )
