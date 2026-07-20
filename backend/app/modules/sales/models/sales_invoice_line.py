"""Sales invoice line model."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity

if TYPE_CHECKING:
    from app.modules.sales.models.sales_invoice import SalesInvoice


class SalesInvoiceLine(BaseEntity):
    """Line item owned by one sales invoice."""

    __tablename__ = "sales_invoice_lines"
    __table_args__ = (
        Index("ix_sales_invoice_lines_invoice_id", "invoice_id"),
        Index("ix_sales_invoice_lines_catalog_item_id", "catalog_item_id"),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("sales_invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    catalog_item_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("catalog_items.id", ondelete="RESTRICT"),
        nullable=True,
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )
    discount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    cgst_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    sgst_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    igst_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    cess_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    invoice: Mapped[SalesInvoice] = relationship(back_populates="lines")
