"""Document automation API dependencies."""

from collections.abc import Callable
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.events import EventDispatcher
from app.common.unit_of_work import SQLAlchemyUnitOfWork
from app.core.database import database_state, initialize_database
from app.modules.documents.automation.services import (
    AutomationUnitOfWork,
    DocumentAutomationService,
)
from app.modules.documents.automation.strategies import (
    ExpenseAutomationStrategy,
    PurchaseAutomationStrategy,
    SalesAutomationStrategy,
)
from app.modules.documents.review.api.dependencies import get_document_review_service
from app.modules.expenses.api.dependencies import get_expense_service
from app.modules.purchases.api.dependencies import get_purchase_service
from app.modules.sales.api.dependencies import get_sales_invoice_service


def get_session_factory() -> Callable[[], AsyncSession]:
    """Return the configured async session factory."""
    if database_state.session_factory is None:
        initialize_database()

    if database_state.session_factory is None:
        raise RuntimeError("Database session factory is not initialized")

    return database_state.session_factory


def get_event_dispatcher() -> EventDispatcher:
    """Provide an event dispatcher."""
    return EventDispatcher()


def get_automation_unit_of_work() -> object:
    """Provide automation Unit of Work for authorization helpers."""
    return SQLAlchemyUnitOfWork(get_session_factory())


def get_document_automation_service() -> DocumentAutomationService:
    """Provide document automation service."""
    session_factory = get_session_factory()
    return DocumentAutomationService(
        unit_of_work_factory=cast(
            Callable[[], AutomationUnitOfWork],
            lambda: SQLAlchemyUnitOfWork(session_factory),
        ),
        review_service=get_document_review_service(),
        strategies=[
            SalesAutomationStrategy(sales_service=get_sales_invoice_service()),
            PurchaseAutomationStrategy(purchase_service=get_purchase_service()),
            ExpenseAutomationStrategy(expense_service=get_expense_service()),
        ],
        event_dispatcher=get_event_dispatcher(),
    )
