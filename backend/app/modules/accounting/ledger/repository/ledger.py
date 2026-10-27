"""General Ledger repository."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.pagination import Page, PaginationParams
from app.common.repositories import BaseRepository
from app.modules.accounting.chart_of_accounts.models import (
    Account,
    AccountType,
)
from app.modules.accounting.ledger.models import GeneralLedgerEntry

CREDIT_NORMAL_CATEGORIES = {"liability", "equity", "revenue"}


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

    async def exists_for_source(
        self,
        source_entity: str,
        source_entity_id: uuid.UUID,
    ) -> bool:
        """Return whether ledger entries already exist for a source entity."""
        statement = select(GeneralLedgerEntry.id).where(
            GeneralLedgerEntry.source_entity == source_entity,
            GeneralLedgerEntry.source_entity_id == source_entity_id,
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
        return await self.list_entries(business_id=business_id, pagination=pagination)

    async def list_entries(
        self,
        business_id: uuid.UUID,
        *,
        account_id: uuid.UUID | None = None,
        account_code: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        source_module: str | None = None,
        pagination: PaginationParams | None = None,
    ) -> Page[GeneralLedgerEntry]:
        """Return paginated General Ledger entries with running balances."""
        statement = self._base_statement().where(
            GeneralLedgerEntry.business_id == business_id
        )

        resolved_account_id = account_id
        if account_code is not None and resolved_account_id is None:
            acct_stmt = select(Account.id).where(
                Account.business_id == business_id,
                Account.account_code == account_code,
                Account.is_deleted.is_(False),
            )
            acct_res = await self.session.execute(acct_stmt)
            resolved_account_id = acct_res.scalar_one_or_none()
            if resolved_account_id is None:
                params = pagination or PaginationParams()
                return Page.create(items=[], total=0, params=params)

        if resolved_account_id is not None:
            statement = statement.where(
                GeneralLedgerEntry.account_id == resolved_account_id
            )

        if date_from is not None:
            statement = statement.where(
                GeneralLedgerEntry.transaction_date >= date_from
            )

        if date_to is not None:
            statement = statement.where(
                GeneralLedgerEntry.transaction_date <= date_to
            )

        if source_module is not None:
            statement = statement.where(
                GeneralLedgerEntry.source_module == source_module
            )

        page = await self._paginate(statement, pagination)

        if resolved_account_id is not None and page.items:
            first_item = page.items[0]
            target_account = first_item.account
            category_name = (
                target_account.account_type.category.name.lower()
                if target_account
                and target_account.account_type
                and target_account.account_type.category
                else "asset"
            )
            is_debit_normal = category_name not in CREDIT_NORMAL_CATEGORIES

            prior_stmt = (
                select(
                    func.coalesce(
                        func.sum(GeneralLedgerEntry.debit), Decimal("0.00")
                    ).label("sum_debit"),
                    func.coalesce(
                        func.sum(GeneralLedgerEntry.credit), Decimal("0.00")
                    ).label("sum_credit"),
                )
                .where(
                    GeneralLedgerEntry.business_id == business_id,
                    GeneralLedgerEntry.account_id == resolved_account_id,
                    GeneralLedgerEntry.is_deleted.is_(False),
                    (
                        (
                            GeneralLedgerEntry.transaction_date
                            < first_item.transaction_date
                        )
                        | (
                            (
                                GeneralLedgerEntry.transaction_date
                                == first_item.transaction_date
                            )
                            & (
                                (
                                    GeneralLedgerEntry.created_at
                                    < first_item.created_at
                                )
                                | (
                                    (
                                        GeneralLedgerEntry.created_at
                                        == first_item.created_at
                                    )
                                    & (GeneralLedgerEntry.id < first_item.id)
                                )
                            )
                        )
                    ),
                )
            )
            prior_res = await self.session.execute(prior_stmt)
            prior_debit, prior_credit = prior_res.one()
            current_running = (
                (prior_debit - prior_credit)
                if is_debit_normal
                else (prior_credit - prior_debit)
            )

            for item in page.items:
                delta = (
                    (item.debit - item.credit)
                    if is_debit_normal
                    else (item.credit - item.debit)
                )
                current_running += delta
                item.running_balance = current_running
        else:
            for item in page.items:
                item.running_balance = None

        return page

    async def get_historical_account_totals(
        self,
        business_id: uuid.UUID,
        as_of_date: date,
    ) -> dict[uuid.UUID, tuple[Decimal, Decimal]]:
        """Return cumulative debits and credits grouped by account up to as_of_date."""
        statement = (
            select(
                GeneralLedgerEntry.account_id,
                func.coalesce(
                    func.sum(GeneralLedgerEntry.debit), Decimal("0.00")
                ).label("total_debit"),
                func.coalesce(
                    func.sum(GeneralLedgerEntry.credit), Decimal("0.00")
                ).label("total_credit"),
            )
            .where(
                GeneralLedgerEntry.business_id == business_id,
                GeneralLedgerEntry.transaction_date <= as_of_date,
                GeneralLedgerEntry.is_deleted.is_(False),
            )
            .group_by(GeneralLedgerEntry.account_id)
        )
        result = await self.session.execute(statement)
        return {
            row[0]: (Decimal(str(row[1])), Decimal(str(row[2])))
            for row in result.all()
        }

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
                selectinload(GeneralLedgerEntry.account)
                .selectinload(Account.account_type)
                .selectinload(AccountType.category),
            )
            .where(GeneralLedgerEntry.is_deleted.is_(False))
            .order_by(
                GeneralLedgerEntry.transaction_date.asc(),
                GeneralLedgerEntry.created_at.asc(),
                GeneralLedgerEntry.id.asc(),
            )
        )
