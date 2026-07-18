"""Tests for General Ledger posting service."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Self

import pytest

from app.common.events import Event, EventDispatcher
from app.modules.accounting.journal.models import (
    JournalEntry,
    JournalEntryLine,
    JournalStatus,
)
from app.modules.accounting.ledger.events import LedgerPostedEvent
from app.modules.accounting.ledger.exceptions import (
    LedgerAlreadyPostedException,
    LedgerInvalidJournalException,
    LedgerPostingFailedException,
)
from app.modules.accounting.ledger.models import GeneralLedgerEntry
from app.modules.accounting.ledger.services import LedgerPostingService
from app.modules.accounting.ledger.services.ledger_posting_service import (
    LedgerJournalRepository,
    LedgerPersistenceRepository,
)

pytestmark = pytest.mark.asyncio

EXPECTED_LEDGER_ENTRY_COUNT = 2


class FakeJournalRepository:
    """Fake journal repository for ledger posting tests."""

    def __init__(self, journal: JournalEntry | None) -> None:
        """Initialize with a journal."""
        self.journal = journal

    async def get_by_id(self, journal_id: uuid.UUID) -> JournalEntry | None:
        """Return configured journal by id."""
        if self.journal is None or self.journal.id != journal_id:
            return None
        return self.journal


class FakeLedgerRepository:
    """Fake ledger repository for posting tests."""

    def __init__(
        self,
        *,
        already_exists: bool = False,
        fail_create: bool = False,
    ) -> None:
        """Initialize fake persistence behavior."""
        self.already_exists = already_exists
        self.fail_create = fail_create
        self.entries: list[GeneralLedgerEntry] = []

    async def create_entries(
        self,
        entries: list[GeneralLedgerEntry],
    ) -> list[GeneralLedgerEntry]:
        """Persist configured entries or raise a failure."""
        if self.fail_create:
            raise RuntimeError("ledger create failed")
        self.entries.extend(entries)
        return entries

    async def exists_for_journal(self, journal_id: uuid.UUID) -> bool:
        """Return configured duplicate result."""
        _ = journal_id
        return self.already_exists


class FakeLedgerUnitOfWork:
    """Fake Unit of Work for ledger posting tests."""

    def __init__(
        self,
        *,
        journal_repository: FakeJournalRepository,
        ledger_repository: FakeLedgerRepository,
    ) -> None:
        """Initialize fake repositories."""
        self.journals: LedgerJournalRepository = journal_repository
        self.ledgers: LedgerPersistenceRepository = ledger_repository
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


def build_journal(
    *,
    status: JournalStatus = JournalStatus.POSTED,
    posting_date: date | None = date(2026, 4, 2),
) -> JournalEntry:
    """Build a journal entry with two lines."""
    journal_id = uuid.uuid4()
    return JournalEntry(
        id=journal_id,
        business_id=uuid.uuid4(),
        journal_number="JV-0001",
        transaction_date=date(2026, 4, 1),
        posting_date=posting_date,
        description="Posted journal",
        status=status,
        lines=[
            JournalEntryLine(
                id=uuid.uuid4(),
                journal_entry_id=journal_id,
                account_id=uuid.uuid4(),
                debit=Decimal("100.00"),
                credit=Decimal("0.00"),
                description="Debit cash",
            ),
            JournalEntryLine(
                id=uuid.uuid4(),
                journal_entry_id=journal_id,
                account_id=uuid.uuid4(),
                debit=Decimal("0.00"),
                credit=Decimal("100.00"),
                description="Credit revenue",
            ),
        ],
    )


def build_service(
    uow: FakeLedgerUnitOfWork,
    dispatcher: CapturingEventDispatcher,
) -> LedgerPostingService:
    """Build ledger posting service with fake dependencies."""
    return LedgerPostingService(
        unit_of_work_factory=lambda: uow,
        event_dispatcher=dispatcher,
    )


async def test_posted_journal_creates_ledger_entries() -> None:
    """Posted journal lines are converted into ledger entries."""
    journal = build_journal()
    ledger_repository = FakeLedgerRepository()
    uow = FakeLedgerUnitOfWork(
        journal_repository=FakeJournalRepository(journal),
        ledger_repository=ledger_repository,
    )
    service = build_service(uow, CapturingEventDispatcher())

    entries = await service.post_journal_to_ledger(journal.id)

    assert len(entries) == EXPECTED_LEDGER_ENTRY_COUNT
    assert entries == ledger_repository.entries
    assert entries[0].business_id == journal.business_id
    assert entries[0].journal_entry_id == journal.id
    assert entries[0].journal_line_id == journal.lines[0].id
    assert entries[0].account_id == journal.lines[0].account_id
    assert entries[0].transaction_date == journal.transaction_date
    assert entries[0].posting_date == journal.posting_date
    assert entries[0].source_module == "journal"
    assert entries[0].source_entity == "journal_entry"
    assert uow.committed is True


async def test_draft_journal_is_rejected() -> None:
    """Draft journals cannot be posted to the ledger."""
    journal = build_journal(status=JournalStatus.DRAFT, posting_date=None)
    uow = FakeLedgerUnitOfWork(
        journal_repository=FakeJournalRepository(journal),
        ledger_repository=FakeLedgerRepository(),
    )
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(LedgerInvalidJournalException):
        await service.post_journal_to_ledger(journal.id)

    assert uow.committed is False
    assert uow.rolled_back is True


async def test_duplicate_posting_is_prevented() -> None:
    """A journal already in ledger cannot be posted again."""
    journal = build_journal()
    uow = FakeLedgerUnitOfWork(
        journal_repository=FakeJournalRepository(journal),
        ledger_repository=FakeLedgerRepository(already_exists=True),
    )
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(LedgerAlreadyPostedException):
        await service.post_journal_to_ledger(journal.id)

    assert uow.committed is False
    assert uow.rolled_back is True


async def test_ledger_posted_event_is_published() -> None:
    """Ledger posting publishes a ledger posted event."""
    journal = build_journal()
    dispatcher = CapturingEventDispatcher()
    uow = FakeLedgerUnitOfWork(
        journal_repository=FakeJournalRepository(journal),
        ledger_repository=FakeLedgerRepository(),
    )
    service = build_service(uow, dispatcher)

    await service.post_journal_to_ledger(journal.id)

    assert len(dispatcher.events) == 1
    event = dispatcher.events[0]
    assert isinstance(event, LedgerPostedEvent)
    assert event.journal_id == journal.id
    assert event.ledger_entry_count == EXPECTED_LEDGER_ENTRY_COUNT


async def test_rollback_on_ledger_posting_failure() -> None:
    """Unit of Work rolls back when ledger persistence fails."""
    journal = build_journal()
    uow = FakeLedgerUnitOfWork(
        journal_repository=FakeJournalRepository(journal),
        ledger_repository=FakeLedgerRepository(fail_create=True),
    )
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(LedgerPostingFailedException):
        await service.post_journal_to_ledger(journal.id)

    assert uow.committed is False
    assert uow.rolled_back is True
