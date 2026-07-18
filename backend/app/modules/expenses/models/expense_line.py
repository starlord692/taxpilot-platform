"""Expense line model."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity

if TYPE_CHECKING:
    from app.modules.expenses.models.expense import Expense


class ExpenseLine(BaseEntity):
    """Line item owned by one expense."""

    __tablename__ = "expense_lines"
    __table_args__ = (
        Index("ix_expense_lines_expense_id", "expense_id"),
    )

    expense_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("expenses.id", ondelete="CASCADE"),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    expense: Mapped[Expense] = relationship(back_populates="lines")
