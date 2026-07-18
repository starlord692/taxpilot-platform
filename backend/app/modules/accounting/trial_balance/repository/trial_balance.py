"""Trial Balance repository."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from app.modules.accounting.balances.models import AccountBalance
from app.modules.accounting.chart_of_accounts.models import NormalBalance
from app.modules.accounting.trial_balance.models import (
    TrialBalance,
    TrialBalanceAccount,
)

ZERO_AMOUNT = Decimal("0.00")
CREDIT_NORMAL_CATEGORIES = {"liability", "equity", "revenue"}


class TrialBalanceAccountBalanceRepository(Protocol):
    """Account balance repository behavior required by Trial Balance."""

    async def list_business_balances(
        self,
        business_id: uuid.UUID,
    ) -> list[AccountBalance]:
        """Return account balances for a business."""
        ...


class TrialBalanceRepository:
    """Repository for Trial Balance generation from account balances."""

    def __init__(
        self,
        balance_repository: TrialBalanceAccountBalanceRepository,
    ) -> None:
        """Initialize with the account balance repository."""
        self._balance_repository = balance_repository

    async def generate_trial_balance(
        self,
        business_id: uuid.UUID,
        *,
        include_zero_balances: bool = False,
    ) -> TrialBalance:
        """Generate a Trial Balance using account balance read models."""
        balances = await self._balance_repository.list_business_balances(business_id)
        account_rows = [
            self._to_trial_balance_account(balance)
            for balance in balances
            if self._should_include(balance, include_zero_balances)
        ]
        total_debit = sum((account.debit for account in account_rows), ZERO_AMOUNT)
        total_credit = sum((account.credit for account in account_rows), ZERO_AMOUNT)
        return TrialBalance(
            business_id=business_id,
            generated_at=datetime.now(tz=UTC),
            total_debit=total_debit,
            total_credit=total_credit,
            is_balanced=total_debit == total_credit,
            accounts=account_rows,
        )

    def _should_include(
        self,
        balance: AccountBalance,
        include_zero_balances: bool,
    ) -> bool:
        """Return whether a balance row should appear in the Trial Balance."""
        if not balance.account.is_active:
            return False
        return include_zero_balances or balance.current_balance != ZERO_AMOUNT

    def _to_trial_balance_account(
        self,
        balance: AccountBalance,
    ) -> TrialBalanceAccount:
        """Convert one balance row to a Trial Balance account row."""
        account = balance.account
        account_type = account.account_type
        normal_balance = self._normal_balance_for_category(
            account_type.category.name
        )
        balance_amount = balance.current_balance
        debit = ZERO_AMOUNT
        credit = ZERO_AMOUNT

        if normal_balance == NormalBalance.DEBIT:
            if balance_amount >= ZERO_AMOUNT:
                debit = balance_amount
            else:
                credit = abs(balance_amount)
        elif balance_amount <= ZERO_AMOUNT:
            credit = abs(balance_amount)
        else:
            debit = balance_amount

        return TrialBalanceAccount(
            account_id=account.id,
            account_code=account.account_code,
            account_name=account.account_name,
            account_type=account_type.name,
            account_category=account_type.category.name,
            debit=debit,
            credit=credit,
            balance=balance_amount,
        )

    def _normal_balance_for_category(self, category_name: str) -> NormalBalance:
        """Infer normal balance from the account category."""
        if category_name.lower() in CREDIT_NORMAL_CATEGORIES:
            return NormalBalance.CREDIT
        return NormalBalance.DEBIT
