"""Financial statement repository."""

import uuid
from decimal import Decimal
from typing import Protocol

from app.modules.accounting.financial_statements.models import (
    BalanceSheet,
    ProfitAndLossStatement,
    StatementLine,
)
from app.modules.accounting.trial_balance.models import (
    TrialBalance,
    TrialBalanceAccount,
)

ZERO_AMOUNT = Decimal("0.00")
REVENUE_CATEGORY = "revenue"
EXPENSE_CATEGORY = "expense"
ASSET_CATEGORY = "asset"
LIABILITY_CATEGORY = "liability"
EQUITY_CATEGORY = "equity"


class FinancialStatementTrialBalanceRepository(Protocol):
    """Trial Balance repository behavior required by financial statements."""

    async def generate_trial_balance(
        self,
        business_id: uuid.UUID,
        *,
        include_zero_balances: bool = False,
    ) -> TrialBalance:
        """Generate a Trial Balance."""
        ...


class FinancialStatementRepository:
    """Repository for generating financial statements from Trial Balance."""

    def __init__(
        self,
        trial_balance_repository: FinancialStatementTrialBalanceRepository,
    ) -> None:
        """Initialize with the Trial Balance repository."""
        self._trial_balance_repository = trial_balance_repository

    async def generate_profit_and_loss(
        self,
        business_id: uuid.UUID,
    ) -> ProfitAndLossStatement:
        """Generate Profit and Loss Statement from Trial Balance."""
        trial_balance = await self._trial_balance_repository.generate_trial_balance(
            business_id
        )
        revenue = [
            self._to_statement_line(account, amount=account.credit - account.debit)
            for account in trial_balance.accounts
            if self._category(account) == REVENUE_CATEGORY
        ]
        expenses = [
            self._to_statement_line(account, amount=account.debit - account.credit)
            for account in trial_balance.accounts
            if self._category(account) == EXPENSE_CATEGORY
        ]
        total_revenue = self._sum_lines(revenue)
        total_expenses = self._sum_lines(expenses)
        return ProfitAndLossStatement(
            business_id=business_id,
            generated_at=trial_balance.generated_at,
            revenue=revenue,
            expenses=expenses,
            total_revenue=total_revenue,
            total_expenses=total_expenses,
            net_profit=total_revenue - total_expenses,
        )

    async def generate_balance_sheet(self, business_id: uuid.UUID) -> BalanceSheet:
        """Generate Balance Sheet from Trial Balance."""
        trial_balance = await self._trial_balance_repository.generate_trial_balance(
            business_id
        )
        assets = [
            self._to_statement_line(account, amount=account.debit - account.credit)
            for account in trial_balance.accounts
            if self._category(account) == ASSET_CATEGORY
        ]
        liabilities = [
            self._to_statement_line(account, amount=account.credit - account.debit)
            for account in trial_balance.accounts
            if self._category(account) == LIABILITY_CATEGORY
        ]
        equity = [
            self._to_statement_line(account, amount=account.credit - account.debit)
            for account in trial_balance.accounts
            if self._category(account) == EQUITY_CATEGORY
        ]
        total_assets = self._sum_lines(assets)
        total_liabilities = self._sum_lines(liabilities)
        total_equity = self._sum_lines(equity)
        return BalanceSheet(
            business_id=business_id,
            generated_at=trial_balance.generated_at,
            assets=assets,
            liabilities=liabilities,
            equity=equity,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            total_equity=total_equity,
            is_balanced=total_assets == total_liabilities + total_equity,
        )

    def _to_statement_line(
        self,
        account: TrialBalanceAccount,
        *,
        amount: Decimal,
    ) -> StatementLine:
        """Convert a Trial Balance account to a statement line."""
        return StatementLine(
            account_id=account.account_id,
            account_code=account.account_code,
            account_name=account.account_name,
            account_type=account.account_type,
            amount=amount,
        )

    def _sum_lines(self, lines: list[StatementLine]) -> Decimal:
        """Sum statement line amounts."""
        return sum((line.amount for line in lines), ZERO_AMOUNT)

    def _category(self, account: TrialBalanceAccount) -> str:
        """Return normalized account category."""
        return account.account_category.lower()
