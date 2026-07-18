"""Tests for account balance service."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Self

import pytest

from app.common.events import Event, EventDispatcher
from app.modules.accounting.balances.events import AccountBalanceUpdatedEvent
from app.modules.accounting.balances.models import AccountBalance
from app.modules.accounting.balances.services import AccountBalanceService
from app.modules.accounting.balances.services.balance_service import (
    AccountBalanceLedgerRepository,
    AccountBalancePersistenceRepository,
)
from app.modules.accounting.ledger.models import GeneralLedgerEntry

pytestmark = pytest.mark.asyncio

EXPECTED_MULTI_ACCOUNT_BALANCES = 2


class FakeLedgerRepository:
    """Fake ledger repository for balance service tests."""

    def __init__(self, entries: list[GeneralLedgerEntry]) -> None:
        """Initialize with ledger entries."""
        self.entries = entries

    async def list_by_journal(
        self,
        journal_id: uuid.UUID,
    ) -> list[GeneralLedgerEntry]:
        """Return entries for a journal."""
        return [
            entry
            for entry in self.entries
            if entry.journal_entry_id == journal_id
        ]


class FakeAccountBalanceRepository:
    """Fake account balance repository for service tests."""

    def __init__(self, *, fail_update: bool = False) -> None:
        """Initialize fake persistence behavior."""
        self.fail_update = fail_update
        self.balances: dict[uuid.UUID, AccountBalance] = {}

    async def create_if_missing(
        self,
        *,
        business_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> AccountBalance:
        """Create or return an account balance."""
        if account_id not in self.balances:
            self.balances[account_id] = AccountBalance(
                business_id=business_id,
                account_id=account_id,
                current_debit=Decimal("0.00"),
                current_credit=Decimal("0.00"),
                current_balance=Decimal("0.00"),
            )
        return self.balances[account_id]

    async def update_balance(
        self,
        balance: AccountBalance,
        *,
        debit_delta: Decimal,
        credit_delta: Decimal,
        last_posted_at: datetime,
    ) -> AccountBalance:
        """Update a balance or raise configured failure."""
        if self.fail_update:
            raise RuntimeError("balance update failed")
        balance.current_debit += debit_delta
        balance.current_credit += credit_delta
        balance.current_balance = balance.current_debit - balance.current_credit
        balance.last_posted_at = last_posted_at
        return balance


class FakeBalanceUnitOfWork:
    """Fake Unit of Work for account balance tests."""

    def __init__(
        self,
        *,
        ledger_repository: FakeLedgerRepository,
        balance_repository: FakeAccountBalanceRepository,
    ) -> None:
        """Initialize fake repositories."""
        self.ledgers: AccountBalanceLedgerRepository = ledger_repository
        self.account_balances: AccountBalancePersistenceRepository = (
            balance_repository
        )
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> Self:
        """Enter fake transaction scope."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Rollback uncommitted fake transactions."""
        if exc_type is not None or not self.committed:
            self.rolled_back = True

    async def commit(self) -> None:
        """Mark transaction committed."""
        self.committed = True


class CapturingEventDispatcher(EventDispatcher):
    """Event dispatcher that records dispatched events."""

    def __init__(self) -> None:
        """Initialize captured events."""
        super().__init__()
        self.events: list[Event] = []

    async def dispatch(self, event: Event) -> None:
        """Record and dispatch an event."""
        self.events.append(event)
        await super().dispatch(event)


def build_entry(
    *,
    journal_id: uuid.UUID,
    business_id: uuid.UUID,
    account_id: uuid.UUID,
    debit: Decimal,
    credit: Decimal,
    posting_date: date = date(2026, 4, 1),
) -> GeneralLedgerEntry:
    """Build a ledger entry."""
    return GeneralLedgerEntry(
        id=uuid.uuid4(),
        business_id=business_id,
        journal_entry_id=journal_id,
        journal_line_id=uuid.uuid4(),
        account_id=account_id,
        transaction_date=date(2026, 4, 1),
        posting_date=posting_date,
        debit=debit,
        credit=credit,
    )


def build_service(
    uow: FakeBalanceUnitOfWork,
    dispatcher: CapturingEventDispatcher,
) -> AccountBalanceService:
    """Build account balance service with fake dependencies."""
    return AccountBalanceService(
        unit_of_work_factory=lambda: uow,
        event_dispatcher=dispatcher,
    )


async def test_create_balance_from_ledger_entry() -> None:
    """A missing balance row is created from a ledger entry."""
    journal_id = uuid.uuid4()
    business_id = uuid.uuid4()
    account_id = uuid.uuid4()
    entries = [
        build_entry(
            journal_id=journal_id,
            business_id=business_id,
            account_id=account_id,
            debit=Decimal("100.00"),
            credit=Decimal("0.00"),
        )
    ]
    balance_repository = FakeAccountBalanceRepository()
    uow = FakeBalanceUnitOfWork(
        ledger_repository=FakeLedgerRepository(entries),
        balance_repository=balance_repository,
    )
    service = build_service(uow, CapturingEventDispatcher())

    balances = await service.apply_ledger_entries(journal_id)

    assert len(balances) == 1
    assert balances[0].business_id == business_id
    assert balances[0].account_id == account_id
    assert balances[0].current_debit == Decimal("100.00")
    assert balances[0].current_credit == Decimal("0.00")
    assert balances[0].current_balance == Decimal("100.00")
    assert balances[0].last_posted_at == datetime(2026, 4, 1, tzinfo=UTC)
    assert uow.committed is True


async def test_update_existing_balance() -> None:
    """Existing balances receive debit and credit deltas."""
    journal_id = uuid.uuid4()
    business_id = uuid.uuid4()
    account_id = uuid.uuid4()
    balance_repository = FakeAccountBalanceRepository()
    balance_repository.balances[account_id] = AccountBalance(
        business_id=business_id,
        account_id=account_id,
        current_debit=Decimal("50.00"),
        current_credit=Decimal("10.00"),
        current_balance=Decimal("40.00"),
    )
    entries = [
        build_entry(
            journal_id=journal_id,
            business_id=business_id,
            account_id=account_id,
            debit=Decimal("25.00"),
            credit=Decimal("5.00"),
        )
    ]
    uow = FakeBalanceUnitOfWork(
        ledger_repository=FakeLedgerRepository(entries),
        balance_repository=balance_repository,
    )
    service = build_service(uow, CapturingEventDispatcher())

    balances = await service.apply_ledger_entries(journal_id)

    assert balances[0].current_debit == Decimal("75.00")
    assert balances[0].current_credit == Decimal("15.00")
    assert balances[0].current_balance == Decimal("60.00")


async def test_multiple_ledger_entries_group_by_account() -> None:
    """Multiple ledger entries for one account are aggregated."""
    journal_id = uuid.uuid4()
    business_id = uuid.uuid4()
    account_id = uuid.uuid4()
    entries = [
        build_entry(
            journal_id=journal_id,
            business_id=business_id,
            account_id=account_id,
            debit=Decimal("100.00"),
            credit=Decimal("0.00"),
        ),
        build_entry(
            journal_id=journal_id,
            business_id=business_id,
            account_id=account_id,
            debit=Decimal("25.00"),
            credit=Decimal("5.00"),
            posting_date=date(2026, 4, 2),
        ),
    ]
    uow = FakeBalanceUnitOfWork(
        ledger_repository=FakeLedgerRepository(entries),
        balance_repository=FakeAccountBalanceRepository(),
    )
    service = build_service(uow, CapturingEventDispatcher())

    balances = await service.apply_ledger_entries(journal_id)

    assert len(balances) == 1
    assert balances[0].current_debit == Decimal("125.00")
    assert balances[0].current_credit == Decimal("5.00")
    assert balances[0].current_balance == Decimal("120.00")
    assert balances[0].last_posted_at == datetime(2026, 4, 2, tzinfo=UTC)


async def test_multiple_accounts_create_multiple_balances() -> None:
    """Ledger entries for different accounts update separate balances."""
    journal_id = uuid.uuid4()
    business_id = uuid.uuid4()
    account_ids = [uuid.uuid4(), uuid.uuid4()]
    entries = [
        build_entry(
            journal_id=journal_id,
            business_id=business_id,
            account_id=account_ids[0],
            debit=Decimal("100.00"),
            credit=Decimal("0.00"),
        ),
        build_entry(
            journal_id=journal_id,
            business_id=business_id,
            account_id=account_ids[1],
            debit=Decimal("0.00"),
            credit=Decimal("100.00"),
        ),
    ]
    uow = FakeBalanceUnitOfWork(
        ledger_repository=FakeLedgerRepository(entries),
        balance_repository=FakeAccountBalanceRepository(),
    )
    service = build_service(uow, CapturingEventDispatcher())

    balances = await service.apply_ledger_entries(journal_id)

    assert len(balances) == EXPECTED_MULTI_ACCOUNT_BALANCES
    assert {balance.account_id for balance in balances} == set(account_ids)


async def test_event_published_after_balance_update() -> None:
    """Balance updates publish account balance updated event."""
    journal_id = uuid.uuid4()
    business_id = uuid.uuid4()
    account_id = uuid.uuid4()
    dispatcher = CapturingEventDispatcher()
    entries = [
        build_entry(
            journal_id=journal_id,
            business_id=business_id,
            account_id=account_id,
            debit=Decimal("100.00"),
            credit=Decimal("0.00"),
        )
    ]
    uow = FakeBalanceUnitOfWork(
        ledger_repository=FakeLedgerRepository(entries),
        balance_repository=FakeAccountBalanceRepository(),
    )
    service = build_service(uow, dispatcher)

    await service.apply_ledger_entries(journal_id)

    assert len(dispatcher.events) == 1
    event = dispatcher.events[0]
    assert isinstance(event, AccountBalanceUpdatedEvent)
    assert event.journal_id == journal_id
    assert event.business_id == business_id
    assert event.account_ids == [account_id]


async def test_rollback_on_balance_update_failure() -> None:
    """Unit of Work rolls back when balance persistence fails."""
    journal_id = uuid.uuid4()
    entries = [
        build_entry(
            journal_id=journal_id,
            business_id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            debit=Decimal("100.00"),
            credit=Decimal("0.00"),
        )
    ]
    uow = FakeBalanceUnitOfWork(
        ledger_repository=FakeLedgerRepository(entries),
        balance_repository=FakeAccountBalanceRepository(fail_update=True),
    )
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(RuntimeError):
        await service.apply_ledger_entries(journal_id)

    assert uow.committed is False
    assert uow.rolled_back is True
