"""Account balance engine service."""

import uuid
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, time
from decimal import Decimal
from typing import Protocol

from app.common.events import EventDispatcher
from app.modules.accounting.balances.events import AccountBalanceUpdatedEvent
from app.modules.accounting.balances.models import AccountBalance
from app.modules.accounting.ledger.models import GeneralLedgerEntry


class AccountBalanceLedgerRepository(Protocol):
    """Ledger repository behavior required by balance updates."""

    async def list_by_journal(
        self,
        journal_id: uuid.UUID,
    ) -> list[GeneralLedgerEntry]:
        """Return ledger entries for a journal."""
        ...


class AccountBalancePersistenceRepository(Protocol):
    """Balance repository behavior required by balance updates."""

    async def create_if_missing(
        self,
        *,
        business_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> AccountBalance:
        """Create or return an account balance."""
        ...

    async def update_balance(
        self,
        balance: AccountBalance,
        *,
        debit_delta: Decimal,
        credit_delta: Decimal,
        last_posted_at: datetime,
    ) -> AccountBalance:
        """Update a balance with ledger deltas."""
        ...


class AccountBalanceUnitOfWork(Protocol):
    """Unit of Work contract required by the balance engine."""

    ledgers: AccountBalanceLedgerRepository
    account_balances: AccountBalancePersistenceRepository

    async def __aenter__(self) -> "AccountBalanceUnitOfWork":
        """Enter the balance transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the balance transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit balance changes."""
        ...


UnitOfWorkFactory = Callable[[], AccountBalanceUnitOfWork]


class AccountBalanceService:
    """Maintain current account balances from General Ledger entries."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
    ) -> None:
        """Initialize with injected dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher

    async def apply_ledger_entries(
        self,
        journal_id: uuid.UUID,
    ) -> list[AccountBalance]:
        """Apply all ledger entries for a journal to account balances."""
        async with self._unit_of_work_factory() as uow:
            ledger_entries = await uow.ledgers.list_by_journal(journal_id)
            if not ledger_entries:
                await uow.commit()
                return []

            balances: list[AccountBalance] = []
            grouped_entries = self._group_by_account(ledger_entries)
            for account_id, entries in grouped_entries.items():
                first_entry = entries[0]
                balance = await uow.account_balances.create_if_missing(
                    business_id=first_entry.business_id,
                    account_id=account_id,
                )
                balances.append(
                    await uow.account_balances.update_balance(
                        balance,
                        debit_delta=sum(
                            (entry.debit for entry in entries),
                            Decimal("0.00"),
                        ),
                        credit_delta=sum(
                            (entry.credit for entry in entries),
                            Decimal("0.00"),
                        ),
                        last_posted_at=self._last_posted_at(entries),
                    )
                )

            await self._event_dispatcher.dispatch(
                AccountBalanceUpdatedEvent(
                    journal_id=journal_id,
                    business_id=ledger_entries[0].business_id,
                    account_ids=list(grouped_entries.keys()),
                )
            )
            await uow.commit()
            return balances

    def _group_by_account(
        self,
        entries: Iterable[GeneralLedgerEntry],
    ) -> dict[uuid.UUID, list[GeneralLedgerEntry]]:
        """Group ledger entries by account."""
        grouped: dict[uuid.UUID, list[GeneralLedgerEntry]] = defaultdict(list)
        for entry in entries:
            grouped[entry.account_id].append(entry)
        return dict(grouped)

    def _last_posted_at(self, entries: list[GeneralLedgerEntry]) -> datetime:
        """Return a timezone-aware timestamp from the latest posting date."""
        latest_posting_date = max(entry.posting_date for entry in entries)
        return datetime.combine(latest_posting_date, time.min, tzinfo=UTC)
