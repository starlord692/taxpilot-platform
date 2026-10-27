"""Accounting API dependencies."""

from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.unit_of_work import SQLAlchemyUnitOfWork
from app.core.database import database_state, initialize_database
from app.modules.accounting.trial_balance.services import TrialBalanceService


def get_session_factory() -> Callable[[], AsyncSession]:
    """Return the configured async session factory."""
    if database_state.session_factory is None:
        initialize_database()

    if database_state.session_factory is None:
        raise RuntimeError("Database session factory is not initialized")

    return database_state.session_factory


def get_accounting_unit_of_work() -> Any:
    """Provide an Accounting Unit of Work."""
    session_factory = get_session_factory()
    return SQLAlchemyUnitOfWork(session_factory)


def get_trial_balance_service() -> TrialBalanceService:
    """Provide the Trial Balance service."""
    session_factory = get_session_factory()
    return TrialBalanceService(
        unit_of_work_factory=lambda: SQLAlchemyUnitOfWork(session_factory)
    )
