"""General Ledger posting service."""

import uuid
from collections.abc import Callable
from typing import Protocol

from app.common.events import EventDispatcher
from app.modules.accounting.journal.models import JournalEntry, JournalStatus
from app.modules.accounting.ledger.events import LedgerPostedEvent
from app.modules.accounting.ledger.exceptions import (
    LedgerAlreadyPostedException,
    LedgerInvalidJournalException,
    LedgerPostingFailedException,
)
from app.modules.accounting.ledger.models import GeneralLedgerEntry


class LedgerJournalRepository(Protocol):
    """Journal repository behavior required by ledger posting."""

    async def get_by_id(self, journal_id: uuid.UUID) -> JournalEntry | None:
        """Return a journal entry by UUID."""
        ...


class LedgerPersistenceRepository(Protocol):
    """Ledger repository behavior required by ledger posting."""

    async def create_entries(
        self,
        entries: list[GeneralLedgerEntry],
    ) -> list[GeneralLedgerEntry]:
        """Persist ledger entries."""
        ...

    async def exists_for_journal(self, journal_id: uuid.UUID) -> bool:
        """Return whether a journal is already posted to ledger."""
        ...


class LedgerPostingUnitOfWork(Protocol):
    """Unit of Work contract required by ledger posting."""

    journals: LedgerJournalRepository
    ledgers: LedgerPersistenceRepository

    async def __aenter__(self) -> "LedgerPostingUnitOfWork":
        """Enter the ledger posting transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the ledger posting transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit ledger posting changes."""
        ...


UnitOfWorkFactory = Callable[[], LedgerPostingUnitOfWork]


class LedgerPostingService:
    """Convert posted journal entries into immutable ledger entries."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
    ) -> None:
        """Initialize the service with injected dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher

    async def post_journal_to_ledger(
        self,
        journal_id: uuid.UUID,
    ) -> list[GeneralLedgerEntry]:
        """Post a journal entry's lines to the General Ledger."""
        async with self._unit_of_work_factory() as uow:
            journal = await uow.journals.get_by_id(journal_id)
            if journal is None:
                raise LedgerInvalidJournalException(
                    "Journal entry is required for ledger posting",
                    details={"journal_id": str(journal_id)},
                )
            self._ensure_posted_journal(journal)

            if await uow.ledgers.exists_for_journal(journal_id):
                raise LedgerAlreadyPostedException(
                    "Journal entry has already been posted to the ledger",
                    details={"journal_id": str(journal_id)},
                )

            entries = self._build_entries(journal)
            try:
                entries = await uow.ledgers.create_entries(entries)
                await self._event_dispatcher.dispatch(
                    LedgerPostedEvent(
                        journal_id=journal.id,
                        ledger_entry_count=len(entries),
                    )
                )
            except Exception as exc:
                raise LedgerPostingFailedException(
                    "Ledger posting failed",
                    details={"journal_id": str(journal_id)},
                ) from exc

            await uow.commit()
            return entries

    async def rebuild_ledger(self, journal_id: uuid.UUID) -> None:
        """Future hook for compensating ledger rebuilds."""
        _ = journal_id

    def _ensure_posted_journal(self, journal: JournalEntry) -> None:
        """Raise if a journal is not eligible for ledger posting."""
        if journal.status != JournalStatus.POSTED:
            raise LedgerInvalidJournalException(
                "Only posted journal entries can be posted to the ledger",
                details={
                    "journal_id": str(journal.id),
                    "status": journal.status.value,
                },
            )
        if journal.posting_date is None:
            raise LedgerInvalidJournalException(
                "Posted journal entry must have a posting date",
                details={"journal_id": str(journal.id)},
            )

    def _build_entries(self, journal: JournalEntry) -> list[GeneralLedgerEntry]:
        """Build ledger entries from journal lines."""
        posting_date = journal.posting_date
        if posting_date is None:
            raise LedgerInvalidJournalException(
                "Posted journal entry must have a posting date",
                details={"journal_id": str(journal.id)},
            )
        return [
            GeneralLedgerEntry(
                business_id=journal.business_id,
                journal_entry_id=journal.id,
                journal_line_id=line.id,
                account_id=line.account_id,
                transaction_date=journal.transaction_date,
                posting_date=posting_date,
                debit=line.debit,
                credit=line.credit,
                description=line.description or journal.description,
                source_module="journal",
                source_entity="journal_entry",
                source_entity_id=journal.id,
            )
            for line in journal.lines
        ]
