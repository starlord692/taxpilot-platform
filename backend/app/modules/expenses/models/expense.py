"""Expense model."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.modules.expenses.models.enums import ExpenseCategory, ExpenseStatus

if TYPE_CHECKING:
    from app.modules.business.models import Business
    from app.modules.expenses.models.expense_line import ExpenseLine
    from app.modules.expenses.models.vendor import Vendor


class Expense(BaseEntity):
    """Expense transaction owned by one business."""

    __tablename__ = "expenses"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "expense_number",
            name="uq_expenses_business_expense_number",
        ),
        Index("ix_expenses_business_id", "business_id"),
        Index("ix_expenses_vendor_id", "vendor_id"),
        Index("ix_expenses_expense_number", "expense_number"),
        Index("ix_expenses_expense_date", "expense_date"),
        Index("ix_expenses_category", "category"),
        Index("ix_expenses_status", "status"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="SET NULL"),
        nullable=True,
    )
    expense_number: Mapped[str] = mapped_column(String(50), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[ExpenseCategory] = mapped_column(
        Enum(ExpenseCategory, name="expense_category"),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ExpenseStatus] = mapped_column(
        Enum(ExpenseStatus, name="expense_status"),
        default=ExpenseStatus.DRAFT,
        nullable=False,
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    business: Mapped[Business] = relationship()
    vendor: Mapped[Vendor | None] = relationship(back_populates="expenses")
    lines: Mapped[list[ExpenseLine]] = relationship(
        back_populates="expense",
        cascade="all, delete-orphan",
    )
