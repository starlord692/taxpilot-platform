"""Tests for Trial Balance engine."""

import uuid
from decimal import Decimal
from typing import Self

import pytest

from app.modules.accounting.balances.models import AccountBalance
from app.modules.accounting.chart_of_accounts.models import (
    Account,
    AccountCategory,
    AccountType,
)
from app.modules.accounting.trial_balance.models import TrialBalance
from app.modules.accounting.trial_balance.repository import TrialBalanceRepository
from app.modules.accounting.trial_balance.services import TrialBalanceService
from app.modules.accounting.trial_balance.services.trial_balance_service import (
    TrialBalancePersistenceRepository,
)

pytestmark = pytest.mark.asyncio

EXPECTED_ACCOUNT_COUNT = 2


class FakeAccountBalanceRepository:
    """Fake account balance repository for Trial Balance tests."""

    def __init__(self, balances: list[AccountBalance]) -> None:
        """Initialize with account balances."""
        self.balances = balances

    async def list_business_balances(
        self,
        business_id: uuid.UUID,
    ) -> list[AccountBalance]:
        """Return balances scoped to a business."""
        return [
            balance
            for balance in self.balances
            if balance.business_id == business_id
        ]


class FakeTrialBalanceUnitOfWork:
    """Fake Unit of Work for Trial Balance service tests."""

    def __init__(self, repository: TrialBalancePersistenceRepository) -> None:
        """Initialize with Trial Balance repository."""
        self.trial_balances = repository

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
    business_id: uuid.UUID,
    code: str,
    name: str,
    account_type_name: str,
    category_name: str,
    is_active: bool = True,
) -> Account:
    """Build an account with type and category metadata."""
    category = AccountCategory(id=uuid.uuid4(), name=category_name)
    account_type = AccountType(
        id=uuid.uuid4(),
        category_id=category.id,
        name=account_type_name,
        category=category,
    )
    return Account(
        id=uuid.uuid4(),
        business_id=business_id,
        account_code=code,
        account_name=name,
        account_type_id=account_type.id,
        account_type=account_type,
        is_active=is_active,
    )


def build_balance(
    *,
    business_id: uuid.UUID,
    account: Account,
    debit: Decimal,
    credit: Decimal,
) -> AccountBalance:
    """Build an account balance with account metadata."""
    return AccountBalance(
        business_id=business_id,
        account_id=account.id,
        account=account,
        current_debit=debit,
        current_credit=credit,
        current_balance=debit - credit,
    )


def build_service(balances: list[AccountBalance]) -> TrialBalanceService:
    """Build Trial Balance service using fake repositories."""
    repository = TrialBalanceRepository(FakeAccountBalanceRepository(balances))
    uow = FakeTrialBalanceUnitOfWork(repository)
    return TrialBalanceService(unit_of_work_factory=lambda: uow)


async def test_balanced_trial_balance() -> None:
    """Balanced account balances generate a balanced Trial Balance."""
    business_id = uuid.uuid4()
    cash = build_account(
        business_id=business_id,
        code="1000",
        name="Cash",
        account_type_name="Current Asset",
        category_name="Asset",
    )
    sales = build_account(
        business_id=business_id,
        code="4000",
        name="Sales",
        account_type_name="Operating Revenue",
        category_name="Revenue",
    )
    service = build_service(
        [
            build_balance(
                business_id=business_id,
                account=cash,
                debit=Decimal("100.00"),
                credit=Decimal("0.00"),
            ),
            build_balance(
                business_id=business_id,
                account=sales,
                debit=Decimal("0.00"),
                credit=Decimal("100.00"),
            ),
        ]
    )

    trial_balance = await service.generate(business_id)

    assert isinstance(trial_balance, TrialBalance)
    assert trial_balance.total_debit == Decimal("100.00")
    assert trial_balance.total_credit == Decimal("100.00")
    assert trial_balance.is_balanced is True
    assert len(trial_balance.accounts) == EXPECTED_ACCOUNT_COUNT


async def test_unbalanced_trial_balance_does_not_raise() -> None:
    """Unbalanced data returns is_balanced false without raising."""
    business_id = uuid.uuid4()
    cash = build_account(
        business_id=business_id,
        code="1000",
        name="Cash",
        account_type_name="Current Asset",
        category_name="Asset",
    )
    service = build_service(
        [
            build_balance(
                business_id=business_id,
                account=cash,
                debit=Decimal("100.00"),
                credit=Decimal("0.00"),
            )
        ]
    )

    trial_balance = await service.generate(business_id)

    assert trial_balance.total_debit == Decimal("100.00")
    assert trial_balance.total_credit == Decimal("0.00")
    assert trial_balance.is_balanced is False


async def test_multiple_accounts_include_account_metadata() -> None:
    """Trial Balance rows include account metadata and presentation amounts."""
    business_id = uuid.uuid4()
    rent = build_account(
        business_id=business_id,
        code="5200",
        name="Rent Expense",
        account_type_name="Operating Expense",
        category_name="Expense",
    )
    payable = build_account(
        business_id=business_id,
        code="2000",
        name="Accounts Payable",
        account_type_name="Current Liability",
        category_name="Liability",
    )
    service = build_service(
        [
            build_balance(
                business_id=business_id,
                account=rent,
                debit=Decimal("80.00"),
                credit=Decimal("0.00"),
            ),
            build_balance(
                business_id=business_id,
                account=payable,
                debit=Decimal("0.00"),
                credit=Decimal("80.00"),
            ),
        ]
    )

    trial_balance = await service.generate(business_id)

    assert [account.account_code for account in trial_balance.accounts] == [
        "5200",
        "2000",
    ]
    assert trial_balance.accounts[0].account_type == "Operating Expense"
    assert trial_balance.accounts[1].credit == Decimal("80.00")


async def test_zero_balance_filtering() -> None:
    """Zero-balance accounts are hidden unless requested."""
    business_id = uuid.uuid4()
    cash = build_account(
        business_id=business_id,
        code="1000",
        name="Cash",
        account_type_name="Current Asset",
        category_name="Asset",
    )
    service = build_service(
        [
            build_balance(
                business_id=business_id,
                account=cash,
                debit=Decimal("0.00"),
                credit=Decimal("0.00"),
            )
        ]
    )

    default_trial_balance = await service.generate(business_id)
    full_trial_balance = await service.generate(
        business_id,
        include_zero_balances=True,
    )

    assert default_trial_balance.accounts == []
    assert len(full_trial_balance.accounts) == 1


async def test_business_isolation() -> None:
    """Trial Balance only uses balances for the requested business."""
    business_id = uuid.uuid4()
    other_business_id = uuid.uuid4()
    cash = build_account(
        business_id=business_id,
        code="1000",
        name="Cash",
        account_type_name="Current Asset",
        category_name="Asset",
    )
    other_cash = build_account(
        business_id=other_business_id,
        code="1000",
        name="Cash",
        account_type_name="Current Asset",
        category_name="Asset",
    )
    service = build_service(
        [
            build_balance(
                business_id=business_id,
                account=cash,
                debit=Decimal("100.00"),
                credit=Decimal("0.00"),
            ),
            build_balance(
                business_id=other_business_id,
                account=other_cash,
                debit=Decimal("500.00"),
                credit=Decimal("0.00"),
            ),
        ]
    )

    trial_balance = await service.generate(business_id)

    assert trial_balance.business_id == business_id
    assert trial_balance.total_debit == Decimal("100.00")
    assert len(trial_balance.accounts) == 1


async def test_inactive_accounts_are_ignored() -> None:
    """Inactive accounts are not included in the Trial Balance."""
    business_id = uuid.uuid4()
    inactive = build_account(
        business_id=business_id,
        code="9999",
        name="Inactive",
        account_type_name="Current Asset",
        category_name="Asset",
        is_active=False,
    )
    service = build_service(
        [
            build_balance(
                business_id=business_id,
                account=inactive,
                debit=Decimal("100.00"),
                credit=Decimal("0.00"),
            )
        ]
    )

    trial_balance = await service.generate(business_id)

    assert trial_balance.accounts == []
    assert trial_balance.total_debit == Decimal("0.00")
