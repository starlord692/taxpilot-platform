"""Purchase invoice model."""

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
from app.modules.purchases.models.enums import PurchaseStatus

if TYPE_CHECKING:
    from app.modules.business.models import Business
    from app.modules.purchases.models.purchase_invoice_line import (
        PurchaseInvoiceLine,
    )
    from app.modules.purchases.models.supplier import Supplier


class PurchaseInvoice(BaseEntity):
    """Supplier purchase invoice owned by one business."""

    __tablename__ = "purchase_invoices"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "purchase_number",
            name="uq_purchase_invoices_business_purchase_number",
        ),
        Index("ix_purchase_invoices_business_id", "business_id"),
        Index("ix_purchase_invoices_supplier_id", "supplier_id"),
        Index("ix_purchase_invoices_purchase_number", "purchase_number"),
        Index("ix_purchase_invoices_invoice_date", "invoice_date"),
        Index("ix_purchase_invoices_status", "status"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    purchase_number: Mapped[str] = mapped_column(String(50), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[PurchaseStatus] = mapped_column(
        Enum(PurchaseStatus, name="purchase_status"),
        default=PurchaseStatus.DRAFT,
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
    supplier: Mapped[Supplier] = relationship(back_populates="purchase_invoices")
    lines: Mapped[list[PurchaseInvoiceLine]] = relationship(
        back_populates="purchase_invoice",
        cascade="all, delete-orphan",
    )
