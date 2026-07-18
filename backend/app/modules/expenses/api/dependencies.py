"""Expense API dependencies."""

from collections.abc import Callable
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.events import EventDispatcher
from app.common.unit_of_work import SQLAlchemyUnitOfWork
from app.core.database import database_state, initialize_database
from app.modules.accounting.kernel import AccountingKernelService
from app.modules.accounting.kernel.accounting_kernel import AccountingKernelUnitOfWork
from app.modules.expenses.services import ExpenseService, VendorService
from app.modules.expenses.services.expense_service import ExpenseUnitOfWork
from app.modules.expenses.services.vendor_service import VendorUnitOfWork
from app.modules.gst.api.dependencies import get_gst_calculation_service


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


def get_expense_unit_of_work() -> ExpenseUnitOfWork:
    """Provide an Expense Unit of Work."""
    session_factory = get_session_factory()
    return cast(ExpenseUnitOfWork, SQLAlchemyUnitOfWork(session_factory))


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


def get_vendor_service() -> VendorService:
    """Provide the vendor service with injected dependencies."""
    session_factory = get_session_factory()
    unit_of_work_factory = cast(
        Callable[[], VendorUnitOfWork],
        lambda: SQLAlchemyUnitOfWork(session_factory),
    )
    return VendorService(
        unit_of_work_factory=unit_of_work_factory,
        event_dispatcher=get_event_dispatcher(),
    )


def get_expense_service() -> ExpenseService:
    """Provide the expense service with injected dependencies."""
    session_factory = get_session_factory()
    unit_of_work_factory = cast(
        Callable[[], ExpenseUnitOfWork],
        lambda: SQLAlchemyUnitOfWork(session_factory),
    )
    return ExpenseService(
        unit_of_work_factory=unit_of_work_factory,
        event_dispatcher=get_event_dispatcher(),
        accounting_kernel=get_accounting_kernel_service(),
        gst_calculation_service=get_gst_calculation_service(),
    )
