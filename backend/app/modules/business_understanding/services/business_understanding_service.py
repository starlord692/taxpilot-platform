"""Business Understanding orchestration over existing read contracts."""

import uuid
from collections.abc import Callable
from typing import Protocol

from app.modules.accounting.financial_statements.models import (
    ProfitAndLossStatement,
)
from app.modules.business.exceptions import BusinessNotMemberException
from app.modules.business_understanding.schemas import (
    BusinessUnderstandingFact,
    BusinessUnderstandingResponse,
)


class MembershipReader(Protocol):
    """Business membership contract used for authorization."""

    async def is_member(self, *, business_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Return whether the user belongs to the business."""
        ...


class FinancialStatementReader(Protocol):
    """Existing Accounting read contract used by this experience."""

    async def generate_profit_and_loss(
        self,
        business_id: uuid.UUID,
    ) -> ProfitAndLossStatement:
        """Return the current Accounting Profit and Loss statement."""
        ...


class BusinessUnderstandingUnitOfWork(Protocol):
    """Unit of Work boundary required by the read-only experience."""

    business_memberships: MembershipReader
    financial_statements: FinancialStatementReader

    async def __aenter__(self) -> "BusinessUnderstandingUnitOfWork":
        """Enter the read scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the read scope."""
        ...


UnitOfWorkFactory = Callable[[], BusinessUnderstandingUnitOfWork]

CURRENT_STATE_LIMITATIONS = (
    "This view reflects the current Accounting statement and has no explicit "
    "reporting-period context.",
    "Currency is not supplied by the current Accounting statement contract.",
    "This view contains no AI explanation, recommendation, or decision authority.",
)


class BusinessUnderstandingService:
    """Build a narrow, deterministic Business Understanding snapshot."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        """Initialize with an injected Unit of Work factory."""
        self._unit_of_work_factory = unit_of_work_factory

    async def get_snapshot(
        self,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> BusinessUnderstandingResponse:
        """Return current Accounting facts for an authorized business member."""
        async with self._unit_of_work_factory() as uow:
            if not await uow.business_memberships.is_member(
                business_id=business_id,
                user_id=user_id,
            ):
                raise BusinessNotMemberException(
                    "User is not a member of this business",
                    details={"business_id": str(business_id)},
                )

            statement = await uow.financial_statements.generate_profit_and_loss(
                business_id
            )

        facts = (
            BusinessUnderstandingFact(
                name="total_revenue",
                value=statement.total_revenue,
                source="ACCOUNTING_PROFIT_AND_LOSS",
                classification="SYSTEM_CALCULATION",
            ),
            BusinessUnderstandingFact(
                name="total_expenses",
                value=statement.total_expenses,
                source="ACCOUNTING_PROFIT_AND_LOSS",
                classification="SYSTEM_CALCULATION",
            ),
            BusinessUnderstandingFact(
                name="net_profit",
                value=statement.net_profit,
                source="ACCOUNTING_PROFIT_AND_LOSS",
                classification="SYSTEM_CALCULATION",
            ),
        )
        return BusinessUnderstandingResponse(
            business_id=business_id,
            generated_at=statement.generated_at,
            facts=facts,
            limitations=CURRENT_STATE_LIMITATIONS,
        )
