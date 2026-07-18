"""Immutable General Ledger entry model."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity

if TYPE_CHECKING:
    from app.modules.accounting.chart_of_accounts.models import Account
    from app.modules.accounting.journal.models import JournalEntry, JournalEntryLine
    from app.modules.business.models import Business


class GeneralLedgerEntry(BaseEntity):
    """Immutable ledger entry created from a posted journal entry line."""

    __tablename__ = "general_ledger_entries"
    __table_args__ = (
        Index("ix_general_ledger_entries_business_id", "business_id"),
        Index("ix_general_ledger_entries_journal_entry_id", "journal_entry_id"),
        Index("ix_general_ledger_entries_journal_line_id", "journal_line_id"),
        Index("ix_general_ledger_entries_account_id", "account_id"),
        Index("ix_general_ledger_entries_transaction_date", "transaction_date"),
        Index("ix_general_ledger_entries_posting_date", "posting_date"),
        Index("ix_general_ledger_entries_source", "source_module", "source_entity"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="RESTRICT"),
        nullable=False,
    )
    journal_line_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("journal_entry_lines.id", ondelete="RESTRICT"),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    posting_date: Mapped[date] = mapped_column(Date, nullable=False)
    debit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    credit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    running_balance: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_module: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_entity: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        nullable=True,
    )

    business: Mapped[Business] = relationship()
    journal_entry: Mapped[JournalEntry] = relationship()
    journal_line: Mapped[JournalEntryLine] = relationship()
    account: Mapped[Account] = relationship()
