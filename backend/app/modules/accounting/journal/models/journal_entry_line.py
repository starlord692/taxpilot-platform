"""Journal entry line model."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity

if TYPE_CHECKING:
    from app.modules.accounting.chart_of_accounts.models import Account
    from app.modules.accounting.journal.models.journal_entry import JournalEntry


class JournalEntryLine(BaseEntity):
    """Journal entry line referencing one chart account."""

    __tablename__ = "journal_entry_lines"
    __table_args__ = (
        Index("ix_journal_entry_lines_journal_entry_id", "journal_entry_id"),
        Index("ix_journal_entry_lines_account_id", "account_id"),
    )

    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
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
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    journal_entry: Mapped[JournalEntry] = relationship(back_populates="lines")
    account: Mapped[Account] = relationship()
