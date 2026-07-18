"""Sales invoice payment model."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.modules.sales.models.enums import PaymentMethod

if TYPE_CHECKING:
    from app.modules.sales.models.sales_invoice import SalesInvoice


class Payment(BaseEntity):
    """Payment recorded against one sales invoice."""

    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_invoice_id", "invoice_id"),
        Index("ix_payments_payment_date", "payment_date"),
        Index("ix_payments_payment_method", "payment_method"),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("sales_invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method"),
        nullable=False,
    )
    reference_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    invoice: Mapped[SalesInvoice] = relationship(back_populates="payments")
