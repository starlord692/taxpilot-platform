"""Sales invoice model."""

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
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.modules.sales.models.enums import InvoiceStatus

if TYPE_CHECKING:
    from app.modules.business.models import Business
    from app.modules.sales.models.customer import Customer
    from app.modules.sales.models.payment import Payment
    from app.modules.sales.models.sales_invoice_line import SalesInvoiceLine


class SalesInvoice(BaseEntity):
    """Sales invoice for one customer."""

    __tablename__ = "sales_invoices"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "invoice_number",
            name="uq_sales_invoices_business_invoice_number",
        ),
        Index("ix_sales_invoices_business_id", "business_id"),
        Index("ix_sales_invoices_customer_id", "customer_id"),
        Index("ix_sales_invoices_invoice_number", "invoice_number"),
        Index("ix_sales_invoices_invoice_date", "invoice_date"),
        Index("ix_sales_invoices_status", "status"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status"),
        default=InvoiceStatus.DRAFT,
        nullable=False,
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    taxable_amount: Mapped[Decimal] = mapped_column(
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
    round_off: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0.00"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    business: Mapped[Business] = relationship()
    customer: Mapped[Customer] = relationship(back_populates="invoices")
    lines: Mapped[list[SalesInvoiceLine]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list[Payment]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
    )
