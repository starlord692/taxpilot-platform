"""Journal repository."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.repositories import BaseRepository
from app.modules.accounting.journal.models import (
    JournalEntry,
    JournalEntryLine,
    JournalStatus,
)


class JournalRepository(BaseRepository[JournalEntry]):
    """Repository for journal entry persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, JournalEntry)

    async def get_by_id(self, journal_id: uuid.UUID) -> JournalEntry | None:
        """Return a journal entry with lines and accounts loaded."""
        statement = (
            select(JournalEntry)
            .options(
                selectinload(JournalEntry.lines).selectinload(
                    JournalEntryLine.account
                )
            )
            .where(
                JournalEntry.id == journal_id,
                JournalEntry.is_deleted.is_(False),
            )
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def mark_posted(
        self,
        journal: JournalEntry,
        *,
        posting_date: date,
    ) -> JournalEntry:
        """Mark a journal entry as posted."""
        journal.status = JournalStatus.POSTED
        journal.posting_date = posting_date
        self.session.add(journal)
        await self.session.flush()
        return journal

    async def mark_reversed(self, journal: JournalEntry) -> JournalEntry:
        """Mark a journal entry as reversed."""
        journal.status = JournalStatus.REVERSED
        self.session.add(journal)
        await self.session.flush()
        return journal
