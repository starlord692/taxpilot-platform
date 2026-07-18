"""Tests for journal posting service."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Self

import pytest

from app.common.events import Event, EventDispatcher
from app.modules.accounting.chart_of_accounts.models import Account
from app.modules.accounting.journal.events import (
    JournalPostedEvent,
    JournalReversedEvent,
)
from app.modules.accounting.journal.exceptions import (
    JournalAccountInactiveException,
    JournalInvalidStatusException,
    JournalUnbalancedException,
)
from app.modules.accounting.journal.models import (
    JournalEntry,
    JournalEntryLine,
    JournalStatus,
)
from app.modules.accounting.journal.services import JournalPostingService
from app.modules.accounting.journal.services.posting_service import (
    JournalPostingRepository,
)

pytestmark = pytest.mark.asyncio


class FakeJournalRepository:
    """Fake journal repository for posting service tests."""

    def __init__(
        self,
        *,
        journal: JournalEntry | None = None,
        fail_post: bool = False,
    ) -> None:
        """Initialize fake behavior."""
        self.journal = journal
        self.fail_post = fail_post

    async def get_by_id(self, journal_id: uuid.UUID) -> JournalEntry | None:
        """Return configured journal by id."""
        if self.journal is None or self.journal.id != journal_id:
            return None
        return self.journal

    async def mark_posted(
        self,
        journal: JournalEntry,
        *,
        posting_date: date,
    ) -> JournalEntry:
        """Mark journal posted or raise configured failure."""
        if self.fail_post:
            raise RuntimeError("post failed")
        journal.status = JournalStatus.POSTED
        journal.posting_date = posting_date
        return journal

    async def mark_reversed(self, journal: JournalEntry) -> JournalEntry:
        """Mark journal reversed."""
        journal.status = JournalStatus.REVERSED
        return journal


class FakeJournalUnitOfWork:
    """Fake Unit of Work for posting service tests."""

    def __init__(self, repository: FakeJournalRepository) -> None:
        """Initialize with fake repository."""
        self.journals: JournalPostingRepository = repository
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


def build_account(*, is_active: bool = True) -> Account:
    """Build an account model."""
    return Account(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        account_code="1000",
        account_name="Cash",
        account_type_id=uuid.uuid4(),
        is_active=is_active,
    )


def build_journal(
    *,
    status: JournalStatus = JournalStatus.DRAFT,
    debit: Decimal = Decimal("100.00"),
    credit: Decimal = Decimal("100.00"),
    account_active: bool = True,
) -> JournalEntry:
    """Build a journal entry with two lines."""
    journal_id = uuid.uuid4()
    debit_line = JournalEntryLine(
        id=uuid.uuid4(),
        journal_entry_id=journal_id,
        account_id=uuid.uuid4(),
        debit=debit,
        credit=Decimal("0.00"),
        account=build_account(is_active=account_active),
    )
    credit_line = JournalEntryLine(
        id=uuid.uuid4(),
        journal_entry_id=journal_id,
        account_id=uuid.uuid4(),
        debit=Decimal("0.00"),
        credit=credit,
        account=build_account(is_active=account_active),
    )
    return JournalEntry(
        id=journal_id,
        business_id=uuid.uuid4(),
        journal_number="JV-0001",
        transaction_date=date(2026, 4, 1),
        status=status,
        lines=[debit_line, credit_line],
    )


def build_service(
    uow: FakeJournalUnitOfWork,
    dispatcher: CapturingEventDispatcher,
) -> JournalPostingService:
    """Build posting service with fake dependencies."""
    return JournalPostingService(
        unit_of_work_factory=lambda: uow,
        event_dispatcher=dispatcher,
    )


async def test_balanced_journal_validates() -> None:
    """Balanced draft journal validates successfully."""
    journal = build_journal()
    uow = FakeJournalUnitOfWork(FakeJournalRepository(journal=journal))
    service = build_service(uow, CapturingEventDispatcher())

    result = await service.validate_entry(journal.id)

    assert result.is_valid is True
    assert result.total_debit == Decimal("100.00")
    assert result.total_credit == Decimal("100.00")


async def test_unbalanced_journal_raises_on_post() -> None:
    """Unbalanced journal raises a domain error on post."""
    journal = build_journal(credit=Decimal("90.00"))
    uow = FakeJournalUnitOfWork(FakeJournalRepository(journal=journal))
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(JournalUnbalancedException):
        await service.post_entry(journal.id)

    assert uow.committed is False
    assert uow.rolled_back is True


async def test_inactive_account_raises_on_post() -> None:
    """Inactive line account raises a domain error on post."""
    journal = build_journal(account_active=False)
    uow = FakeJournalUnitOfWork(FakeJournalRepository(journal=journal))
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(JournalAccountInactiveException):
        await service.post_entry(journal.id)


async def test_draft_journal_posts_and_publishes_event() -> None:
    """Draft journal is posted and event is published."""
    journal = build_journal()
    uow = FakeJournalUnitOfWork(FakeJournalRepository(journal=journal))
    dispatcher = CapturingEventDispatcher()
    service = build_service(uow, dispatcher)

    posted = await service.post_entry(journal.id)

    assert posted.status == JournalStatus.POSTED
    assert posted.posting_date is not None
    assert uow.committed is True
    assert isinstance(dispatcher.events[0], JournalPostedEvent)


async def test_posted_journal_reverses_and_publishes_event() -> None:
    """Posted journal is reversed and event is published."""
    journal = build_journal(status=JournalStatus.POSTED)
    uow = FakeJournalUnitOfWork(FakeJournalRepository(journal=journal))
    dispatcher = CapturingEventDispatcher()
    service = build_service(uow, dispatcher)

    reversed_journal = await service.reverse_entry(journal.id)

    assert reversed_journal.status == JournalStatus.REVERSED
    assert uow.committed is True
    assert isinstance(dispatcher.events[0], JournalReversedEvent)


async def test_reverse_non_posted_journal_raises() -> None:
    """Only posted journals can be reversed."""
    journal = build_journal(status=JournalStatus.DRAFT)
    uow = FakeJournalUnitOfWork(FakeJournalRepository(journal=journal))
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(JournalInvalidStatusException):
        await service.reverse_entry(journal.id)

    assert uow.rolled_back is True


async def test_rollback_on_post_failure() -> None:
    """Unit of Work rolls back when posting persistence fails."""
    journal = build_journal()
    uow = FakeJournalUnitOfWork(
        FakeJournalRepository(journal=journal, fail_post=True)
    )
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(RuntimeError):
        await service.post_entry(journal.id)

    assert uow.committed is False
    assert uow.rolled_back is True
