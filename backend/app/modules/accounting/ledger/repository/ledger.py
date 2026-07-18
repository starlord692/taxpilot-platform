"""General Ledger repository."""

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.pagination import Page, PaginationParams
from app.common.repositories import BaseRepository
from app.modules.accounting.ledger.models import GeneralLedgerEntry


class LedgerRepository(BaseRepository[GeneralLedgerEntry]):
    """Repository for immutable General Ledger persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, GeneralLedgerEntry)

    async def create_entry(
        self,
        entry: GeneralLedgerEntry,
    ) -> GeneralLedgerEntry:
        """Create one ledger entry in the current transaction."""
        return await self.add(entry)

    async def create_entries(
        self,
        entries: list[GeneralLedgerEntry],
    ) -> list[GeneralLedgerEntry]:
        """Create multiple ledger entries in the current transaction."""
        self.session.add_all(entries)
        await self.session.flush()
        return entries

    async def exists_for_journal(self, journal_id: uuid.UUID) -> bool:
        """Return whether ledger entries already exist for a journal."""
        statement = select(GeneralLedgerEntry.id).where(
            GeneralLedgerEntry.journal_entry_id == journal_id,
            GeneralLedgerEntry.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none() is not None

    async def list_by_account(
        self,
        account_id: uuid.UUID,
        pagination: PaginationParams | None = None,
    ) -> Page[GeneralLedgerEntry]:
        """Return paginated ledger entries for an account."""
        statement = self._base_statement().where(
            GeneralLedgerEntry.account_id == account_id
        )
        return await self._paginate(statement, pagination)

    async def list_by_business(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
    ) -> Page[GeneralLedgerEntry]:
        """Return paginated ledger entries for a business."""
        statement = self._base_statement().where(
            GeneralLedgerEntry.business_id == business_id
        )
        return await self._paginate(statement, pagination)

    async def list_by_journal(
        self,
        journal_id: uuid.UUID,
    ) -> list[GeneralLedgerEntry]:
        """Return ledger entries for a journal."""
        statement = self._base_statement().where(
            GeneralLedgerEntry.journal_entry_id == journal_id
        )
        result = await self.session.execute(statement)
        return list(result.scalars().unique().all())

    async def _paginate(
        self,
        statement: Select[tuple[GeneralLedgerEntry]],
        pagination: PaginationParams | None,
    ) -> Page[GeneralLedgerEntry]:
        """Paginate a ledger statement."""
        params = pagination or PaginationParams()
        total_statement = select(func.count()).select_from(statement.subquery())
        total_result = await self.session.execute(total_statement)
        result = await self.session.execute(
            statement.offset(params.offset).limit(params.limit)
        )
        return Page.create(
            items=list(result.scalars().unique().all()),
            total=int(total_result.scalar_one()),
            params=params,
        )

    def _base_statement(self) -> Select[tuple[GeneralLedgerEntry]]:
        """Return a standard ledger select with relationships loaded."""
        return (
            select(GeneralLedgerEntry)
            .options(
                selectinload(GeneralLedgerEntry.business),
                selectinload(GeneralLedgerEntry.journal_entry),
                selectinload(GeneralLedgerEntry.journal_line),
                selectinload(GeneralLedgerEntry.account),
            )
            .where(GeneralLedgerEntry.is_deleted.is_(False))
            .order_by(
                GeneralLedgerEntry.transaction_date.asc(),
                GeneralLedgerEntry.created_at.asc(),
            )
        )
