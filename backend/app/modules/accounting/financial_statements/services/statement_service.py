"""Financial statement service."""

import uuid
from collections.abc import Callable
from typing import Protocol

from app.modules.accounting.financial_statements.models import (
    BalanceSheet,
    ProfitAndLossStatement,
)


class FinancialStatementPersistenceRepository(Protocol):
    """Financial statement repository behavior required by the service."""

    async def generate_profit_and_loss(
        self,
        business_id: uuid.UUID,
    ) -> ProfitAndLossStatement:
        """Generate Profit and Loss Statement."""
        ...

    async def generate_balance_sheet(self, business_id: uuid.UUID) -> BalanceSheet:
        """Generate Balance Sheet."""
        ...


class FinancialStatementUnitOfWork(Protocol):
    """Unit of Work contract required by financial statement generation."""

    financial_statements: FinancialStatementPersistenceRepository

    async def __aenter__(self) -> "FinancialStatementUnitOfWork":
        """Enter the financial statement scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the financial statement scope."""
        ...


UnitOfWorkFactory = Callable[[], FinancialStatementUnitOfWork]


class FinancialStatementService:
    """Generate financial statements from Trial Balance."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        """Initialize with injected dependencies."""
        self._unit_of_work_factory = unit_of_work_factory

    async def generate_profit_and_loss(
        self,
        business_id: uuid.UUID,
    ) -> ProfitAndLossStatement:
        """Generate Profit and Loss Statement for a business."""
        async with self._unit_of_work_factory() as uow:
            return await uow.financial_statements.generate_profit_and_loss(
                business_id
            )

    async def generate_balance_sheet(self, business_id: uuid.UUID) -> BalanceSheet:
        """Generate Balance Sheet for a business."""
        async with self._unit_of_work_factory() as uow:
            return await uow.financial_statements.generate_balance_sheet(business_id)
