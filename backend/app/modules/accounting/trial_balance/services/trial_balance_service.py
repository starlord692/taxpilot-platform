"""Trial Balance service."""

import uuid
from collections.abc import Callable
from typing import Protocol

from app.modules.accounting.trial_balance.models import TrialBalance


class TrialBalancePersistenceRepository(Protocol):
    """Trial Balance repository behavior required by the service."""

    async def generate_trial_balance(
        self,
        business_id: uuid.UUID,
        *,
        include_zero_balances: bool = False,
    ) -> TrialBalance:
        """Generate a Trial Balance."""
        ...


class TrialBalanceUnitOfWork(Protocol):
    """Unit of Work contract required by Trial Balance generation."""

    trial_balances: TrialBalancePersistenceRepository

    async def __aenter__(self) -> "TrialBalanceUnitOfWork":
        """Enter the Trial Balance transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the Trial Balance transaction scope."""
        ...


UnitOfWorkFactory = Callable[[], TrialBalanceUnitOfWork]


class TrialBalanceService:
    """Generate Trial Balance read models."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        """Initialize with injected dependencies."""
        self._unit_of_work_factory = unit_of_work_factory

    async def generate(
        self,
        business_id: uuid.UUID,
        *,
        include_zero_balances: bool = False,
    ) -> TrialBalance:
        """Generate a Trial Balance for a business."""
        async with self._unit_of_work_factory() as uow:
            return await uow.trial_balances.generate_trial_balance(
                business_id,
                include_zero_balances=include_zero_balances,
            )
