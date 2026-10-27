import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Protocol

from app.modules.accounting.balances.models import AccountBalance
from app.modules.accounting.chart_of_accounts.models import NormalBalance
from app.modules.accounting.trial_balance.exceptions import (
    TrialBalanceFutureDateException,
)
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
    """Repository for Trial Balance generation from account balances or ledger."""

    def __init__(
        self,
        balance_repository: TrialBalanceAccountBalanceRepository,
        ledger_repository: Any | None = None,
        chart_repository: Any | None = None,
    ) -> None:
        """Initialize with balance repository and optional ledger/chart repositories."""
        self._balance_repository = balance_repository
        self._ledger_repository = ledger_repository
        self._chart_repository = chart_repository

    async def generate_trial_balance(
        self,
        business_id: uuid.UUID,
        *,
        as_of_date: date | None = None,
        include_zero_balances: bool = False,
    ) -> TrialBalance:
        """Generate a Trial Balance using balances or cumulative ledger."""
        current_date = datetime.now(tz=UTC).date()
        effective_date = as_of_date or current_date

        if as_of_date is not None and as_of_date > current_date:
            raise TrialBalanceFutureDateException(
                message=(
                    f"Trial balance cannot be calculated for future date "
                    f"{as_of_date.isoformat()}"
                ),
                details={
                    "as_of_date": as_of_date.isoformat(),
                    "current_date": current_date.isoformat(),
                },
            )

        if as_of_date is not None and as_of_date < current_date:
            if self._ledger_repository is None or self._chart_repository is None:
                raise RuntimeError(
                    "Ledger and Chart repositories required for "
                    "historical Trial Balance calculation"
                )
            account_rows = await self._generate_from_ledger(
                business_id=business_id,
                as_of_date=as_of_date,
                include_zero_balances=include_zero_balances,
            )
        else:
            balances = await self._balance_repository.list_business_balances(
                business_id
            )
            account_rows = [
                self._to_trial_balance_account(balance)
                for balance in balances
                if self._should_include(balance, include_zero_balances)
            ]

        total_debit = sum((account.debit for account in account_rows), ZERO_AMOUNT)
        total_credit = sum((account.credit for account in account_rows), ZERO_AMOUNT)
        discrepancy = total_debit - total_credit
        return TrialBalance(
            business_id=business_id,
            generated_at=datetime.now(tz=UTC),
            as_of_date=effective_date,
            total_debit=total_debit,
            total_credit=total_credit,
            discrepancy=discrepancy,
            is_balanced=discrepancy == ZERO_AMOUNT,
            accounts=account_rows,
        )

    async def _generate_from_ledger(
        self,
        *,
        business_id: uuid.UUID,
        as_of_date: date,
        include_zero_balances: bool,
    ) -> list[TrialBalanceAccount]:
        """Aggregate ledger entries up to as_of_date for active accounts."""
        if self._ledger_repository is None or self._chart_repository is None:
            raise RuntimeError(
                "Ledger and Chart repositories required for "
                "historical Trial Balance calculation"
            )
        totals = await self._ledger_repository.get_historical_account_totals(
            business_id, as_of_date
        )
        accounts = await self._chart_repository.list_accounts(
            business_id=business_id,
            is_active=True,
        )

        rows: list[TrialBalanceAccount] = []
        for account in accounts:
            account_type = account.account_type
            category_name = (
                account_type.category.name
                if account_type and account_type.category
                else "Asset"
            )
            normal_balance = self._normal_balance_for_category(category_name)
            sum_debit, sum_credit = totals.get(account.id, (ZERO_AMOUNT, ZERO_AMOUNT))

            if normal_balance == NormalBalance.DEBIT:
                net_balance = sum_debit - sum_credit
                if net_balance >= ZERO_AMOUNT:
                    debit = net_balance
                    credit = ZERO_AMOUNT
                else:
                    debit = ZERO_AMOUNT
                    credit = abs(net_balance)
                display_balance = net_balance
            else:
                net_balance = sum_credit - sum_debit
                if net_balance >= ZERO_AMOUNT:
                    credit = net_balance
                    debit = ZERO_AMOUNT
                else:
                    credit = ZERO_AMOUNT
                    debit = abs(net_balance)
                display_balance = net_balance

            if (
                not include_zero_balances
                and sum_debit == ZERO_AMOUNT
                and sum_credit == ZERO_AMOUNT
            ):
                continue

            rows.append(
                TrialBalanceAccount(
                    account_id=account.id,
                    account_code=account.account_code,
                    account_name=account.account_name,
                    account_type=account_type.name if account_type else "",
                    account_category=category_name,
                    normal_balance=normal_balance.value,
                    debit=debit,
                    credit=credit,
                    balance=display_balance,
                )
            )

        rows.sort(key=lambda a: a.account_code)
        return rows

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
            normal_balance=normal_balance.value,
            debit=debit,
            credit=credit,
            balance=balance_amount,
        )

    def _normal_balance_for_category(self, category_name: str) -> NormalBalance:
        """Infer normal balance from the account category."""
        if category_name.lower() in CREDIT_NORMAL_CATEGORIES:
            return NormalBalance.CREDIT
        return NormalBalance.DEBIT
