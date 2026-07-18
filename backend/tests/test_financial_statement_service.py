"""Tests for Financial Statement engine."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Self

import pytest

from app.modules.accounting.financial_statements.models import (
    BalanceSheet,
    ProfitAndLossStatement,
)
from app.modules.accounting.financial_statements.repository import (
    FinancialStatementRepository,
)
from app.modules.accounting.financial_statements.services import (
    FinancialStatementService,
)
from app.modules.accounting.financial_statements.services.statement_service import (
    FinancialStatementPersistenceRepository,
)
from app.modules.accounting.trial_balance.models import (
    TrialBalance,
    TrialBalanceAccount,
)

pytestmark = pytest.mark.asyncio


class FakeTrialBalanceRepository:
    """Fake Trial Balance repository for financial statement tests."""

    def __init__(self, trial_balances: dict[uuid.UUID, TrialBalance]) -> None:
        """Initialize with Trial Balances by business."""
        self.trial_balances = trial_balances

    async def generate_trial_balance(
        self,
        business_id: uuid.UUID,
        *,
        include_zero_balances: bool = False,
    ) -> TrialBalance:
        """Return Trial Balance for a business."""
        _ = include_zero_balances
        return self.trial_balances[business_id]


class FakeFinancialStatementUnitOfWork:
    """Fake Unit of Work for financial statement tests."""

    def __init__(self, repository: FinancialStatementPersistenceRepository) -> None:
        """Initialize with financial statement repository."""
        self.financial_statements = repository

    async def __aenter__(self) -> Self:
        """Enter fake scope."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit fake scope."""


def build_account(
    *,
    code: str,
    name: str,
    account_type: str,
    account_category: str,
    debit: Decimal,
    credit: Decimal,
) -> TrialBalanceAccount:
    """Build a Trial Balance account row."""
    return TrialBalanceAccount(
        account_id=uuid.uuid4(),
        account_code=code,
        account_name=name,
        account_type=account_type,
        account_category=account_category,
        debit=debit,
        credit=credit,
        balance=debit - credit,
    )


def build_trial_balance(
    *,
    business_id: uuid.UUID,
    accounts: list[TrialBalanceAccount],
) -> TrialBalance:
    """Build a Trial Balance read model."""
    total_debit = sum((account.debit for account in accounts), Decimal("0.00"))
    total_credit = sum((account.credit for account in accounts), Decimal("0.00"))
    return TrialBalance(
        business_id=business_id,
        generated_at=datetime(2026, 4, 1, tzinfo=UTC),
        total_debit=total_debit,
        total_credit=total_credit,
        is_balanced=total_debit == total_credit,
        accounts=accounts,
    )


def build_service(
    trial_balances: dict[uuid.UUID, TrialBalance],
) -> FinancialStatementService:
    """Build financial statement service with fake dependencies."""
    repository = FinancialStatementRepository(
        FakeTrialBalanceRepository(trial_balances)
    )
    uow = FakeFinancialStatementUnitOfWork(repository)
    return FinancialStatementService(unit_of_work_factory=lambda: uow)


async def test_profit_calculation() -> None:
    """Profit and Loss totals revenue and expenses."""
    business_id = uuid.uuid4()
    service = build_service(
        {
            business_id: build_trial_balance(
                business_id=business_id,
                accounts=[
                    build_account(
                        code="4000",
                        name="Sales",
                        account_type="Operating Revenue",
                        account_category="Revenue",
                        debit=Decimal("0.00"),
                        credit=Decimal("250.00"),
                    ),
                    build_account(
                        code="5200",
                        name="Rent Expense",
                        account_type="Operating Expense",
                        account_category="Expense",
                        debit=Decimal("80.00"),
                        credit=Decimal("0.00"),
                    ),
                ],
            )
        }
    )

    statement = await service.generate_profit_and_loss(business_id)

    assert isinstance(statement, ProfitAndLossStatement)
    assert statement.total_revenue == Decimal("250.00")
    assert statement.total_expenses == Decimal("80.00")


async def test_net_profit() -> None:
    """Profit and Loss calculates net profit."""
    business_id = uuid.uuid4()
    service = build_service(
        {
            business_id: build_trial_balance(
                business_id=business_id,
                accounts=[
                    build_account(
                        code="4000",
                        name="Sales",
                        account_type="Operating Revenue",
                        account_category="Revenue",
                        debit=Decimal("0.00"),
                        credit=Decimal("300.00"),
                    ),
                    build_account(
                        code="5000",
                        name="Cost of Goods Sold",
                        account_type="Cost of Sales",
                        account_category="Expense",
                        debit=Decimal("120.00"),
                        credit=Decimal("0.00"),
                    ),
                ],
            )
        }
    )

    statement = await service.generate_profit_and_loss(business_id)

    assert statement.net_profit == Decimal("180.00")


async def test_balance_sheet_assets_liabilities_and_equity() -> None:
    """Balance Sheet groups assets, liabilities, and equity."""
    business_id = uuid.uuid4()
    service = build_service(
        {
            business_id: build_trial_balance(
                business_id=business_id,
                accounts=[
                    build_account(
                        code="1000",
                        name="Cash",
                        account_type="Current Asset",
                        account_category="Asset",
                        debit=Decimal("500.00"),
                        credit=Decimal("0.00"),
                    ),
                    build_account(
                        code="2000",
                        name="Accounts Payable",
                        account_type="Current Liability",
                        account_category="Liability",
                        debit=Decimal("0.00"),
                        credit=Decimal("200.00"),
                    ),
                    build_account(
                        code="3000",
                        name="Owner Capital",
                        account_type="Equity",
                        account_category="Equity",
                        debit=Decimal("0.00"),
                        credit=Decimal("300.00"),
                    ),
                ],
            )
        }
    )

    statement = await service.generate_balance_sheet(business_id)

    assert isinstance(statement, BalanceSheet)
    assert statement.total_assets == Decimal("500.00")
    assert statement.total_liabilities == Decimal("200.00")
    assert statement.total_equity == Decimal("300.00")


async def test_balanced_balance_sheet() -> None:
    """Balance Sheet flags balanced totals."""
    business_id = uuid.uuid4()
    service = build_service(
        {
            business_id: build_trial_balance(
                business_id=business_id,
                accounts=[
                    build_account(
                        code="1000",
                        name="Cash",
                        account_type="Current Asset",
                        account_category="Asset",
                        debit=Decimal("100.00"),
                        credit=Decimal("0.00"),
                    ),
                    build_account(
                        code="3000",
                        name="Owner Capital",
                        account_type="Equity",
                        account_category="Equity",
                        debit=Decimal("0.00"),
                        credit=Decimal("100.00"),
                    ),
                ],
            )
        }
    )

    statement = await service.generate_balance_sheet(business_id)

    assert statement.is_balanced is True


async def test_business_isolation() -> None:
    """Financial statements use the requested business Trial Balance."""
    business_id = uuid.uuid4()
    other_business_id = uuid.uuid4()
    service = build_service(
        {
            business_id: build_trial_balance(
                business_id=business_id,
                accounts=[
                    build_account(
                        code="4000",
                        name="Sales",
                        account_type="Operating Revenue",
                        account_category="Revenue",
                        debit=Decimal("0.00"),
                        credit=Decimal("50.00"),
                    )
                ],
            ),
            other_business_id: build_trial_balance(
                business_id=other_business_id,
                accounts=[
                    build_account(
                        code="4000",
                        name="Sales",
                        account_type="Operating Revenue",
                        account_category="Revenue",
                        debit=Decimal("0.00"),
                        credit=Decimal("999.00"),
                    )
                ],
            ),
        }
    )

    statement = await service.generate_profit_and_loss(business_id)

    assert statement.business_id == business_id
    assert statement.total_revenue == Decimal("50.00")
