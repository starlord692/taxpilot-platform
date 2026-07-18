"""Journal posting service."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Protocol

from app.common.events import EventDispatcher
from app.modules.accounting.journal.events import (
    JournalPostedEvent,
    JournalReversedEvent,
)
from app.modules.accounting.journal.exceptions import (
    JournalAccountInactiveException,
    JournalInvalidStatusException,
    JournalNotFoundException,
    JournalUnbalancedException,
    JournalValidationFailedException,
)
from app.modules.accounting.journal.models import JournalEntry, JournalStatus

ZERO_AMOUNT = Decimal("0.00")
MINIMUM_JOURNAL_LINES = 2


@dataclass(frozen=True)
class JournalValidationResult:
    """Result returned by journal posting validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    total_debit: Decimal = ZERO_AMOUNT
    total_credit: Decimal = ZERO_AMOUNT


class JournalPostingRepository(Protocol):
    """Journal repository behavior required by posting."""

    async def get_by_id(self, journal_id: uuid.UUID) -> JournalEntry | None:
        """Return a journal entry by UUID."""
        ...

    async def mark_posted(
        self,
        journal: JournalEntry,
        *,
        posting_date: date,
    ) -> JournalEntry:
        """Mark a journal entry as posted."""
        ...

    async def mark_reversed(self, journal: JournalEntry) -> JournalEntry:
        """Mark a journal entry as reversed."""
        ...


class JournalPostingUnitOfWork(Protocol):
    """Unit of Work contract required by journal posting."""

    journals: JournalPostingRepository

    async def __aenter__(self) -> "JournalPostingUnitOfWork":
        """Enter the journal posting transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the journal posting transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit journal posting changes."""
        ...


UnitOfWorkFactory = Callable[[], JournalPostingUnitOfWork]


class JournalPostingService:
    """Validate, post, and reverse journal entries."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
    ) -> None:
        """Initialize the service with injected dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher

    async def validate_entry(self, journal_id: uuid.UUID) -> JournalValidationResult:
        """Validate a journal entry for posting."""
        async with self._unit_of_work_factory() as uow:
            journal = await self._get_journal(uow, journal_id)
            return self._validate_journal(journal)

    async def post_entry(self, journal_id: uuid.UUID) -> JournalEntry:
        """Validate and post a draft journal entry."""
        async with self._unit_of_work_factory() as uow:
            journal = await self._get_journal(uow, journal_id)
            validation = self._validate_journal(journal)
            if not validation.is_valid:
                self._raise_validation_error(validation)

            journal = await uow.journals.mark_posted(
                journal,
                posting_date=datetime.now(tz=UTC).date(),
            )
            await self._event_dispatcher.dispatch(
                JournalPostedEvent(journal_id=journal.id)
            )
            await uow.commit()
            return journal

    async def reverse_entry(self, journal_id: uuid.UUID) -> JournalEntry:
        """Reverse a posted journal entry."""
        async with self._unit_of_work_factory() as uow:
            journal = await self._get_journal(uow, journal_id)
            if journal.status != JournalStatus.POSTED:
                raise JournalInvalidStatusException(
                    "Only posted journal entries can be reversed",
                    details={
                        "journal_id": str(journal_id),
                        "status": journal.status.value,
                    },
                )

            journal = await uow.journals.mark_reversed(journal)
            await self._event_dispatcher.dispatch(
                JournalReversedEvent(journal_id=journal.id)
            )
            await uow.commit()
            return journal

    async def _get_journal(
        self,
        uow: JournalPostingUnitOfWork,
        journal_id: uuid.UUID,
    ) -> JournalEntry:
        """Return a journal entry or raise not found."""
        journal = await uow.journals.get_by_id(journal_id)
        if journal is None:
            raise JournalNotFoundException(
                "Journal entry not found",
                details={"journal_id": str(journal_id)},
            )
        return journal

    def _validate_journal(self, journal: JournalEntry) -> JournalValidationResult:
        """Validate a loaded journal entry."""
        errors: list[str] = []
        total_debit = sum((line.debit for line in journal.lines), ZERO_AMOUNT)
        total_credit = sum((line.credit for line in journal.lines), ZERO_AMOUNT)

        if journal.status != JournalStatus.DRAFT:
            errors.append("journal.invalid_status")
        if len(journal.lines) < MINIMUM_JOURNAL_LINES:
            errors.append("journal.validation_failed")
        if total_debit != total_credit:
            errors.append("journal.unbalanced")
        if any(
            line.debit < ZERO_AMOUNT or line.credit < ZERO_AMOUNT
            for line in journal.lines
        ):
            errors.append("journal.validation_failed")
        if not any(line.debit > ZERO_AMOUNT for line in journal.lines):
            errors.append("journal.validation_failed")
        if not any(line.credit > ZERO_AMOUNT for line in journal.lines):
            errors.append("journal.validation_failed")
        if any(
            line.account is None or not line.account.is_active
            for line in journal.lines
        ):
            errors.append("journal.account_inactive")

        return JournalValidationResult(
            is_valid=not errors,
            errors=errors,
            total_debit=total_debit,
            total_credit=total_credit,
        )

    def _raise_validation_error(
        self,
        validation: JournalValidationResult,
    ) -> None:
        """Raise the most specific validation exception."""
        unique_errors = set(validation.errors)
        if "journal.invalid_status" in unique_errors:
            raise JournalInvalidStatusException("Journal entry must be draft")
        if "journal.account_inactive" in unique_errors:
            raise JournalAccountInactiveException(
                "Journal entry references an inactive account"
            )
        if "journal.unbalanced" in unique_errors:
            raise JournalUnbalancedException(
                "Journal entry debits and credits must balance",
                details={
                    "total_debit": str(validation.total_debit),
                    "total_credit": str(validation.total_credit),
                },
            )
        raise JournalValidationFailedException(
            "Journal entry validation failed",
            details={"errors": validation.errors},
        )
