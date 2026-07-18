"""Journal entry model."""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.modules.accounting.journal.models.enums import JournalStatus

if TYPE_CHECKING:
    from app.modules.accounting.journal.models.journal_entry_line import (
        JournalEntryLine,
    )
    from app.modules.business.models import Business


class JournalEntry(BaseEntity):
    """Journal entry header for double-entry bookkeeping."""

    __tablename__ = "journal_entries"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "journal_number",
            name="uq_journal_entries_business_journal_number",
        ),
        Index("ix_journal_entries_business_id", "business_id"),
        Index("ix_journal_entries_journal_number", "journal_number"),
        Index("ix_journal_entries_transaction_date", "transaction_date"),
        Index("ix_journal_entries_status", "status"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    journal_number: Mapped[str] = mapped_column(String(50), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    posting_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[JournalStatus] = mapped_column(
        Enum(JournalStatus, name="journal_status"),
        default=JournalStatus.DRAFT,
        nullable=False,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        nullable=True,
    )

    business: Mapped[Business] = relationship()
    lines: Mapped[list[JournalEntryLine]] = relationship(
        back_populates="journal_entry",
        cascade="all, delete-orphan",
    )
