"""E-invoice persistence models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.modules.gst.einvoice.models.enums import EInvoiceStatus

if TYPE_CHECKING:
    from app.modules.business.models import Business
    from app.modules.sales.models import SalesInvoice


class EInvoice(BaseEntity):
    """Provider-generated Indian GST e-invoice record."""

    __tablename__ = "gst_einvoices"
    __table_args__ = (
        Index("ix_gst_einvoices_business_id", "business_id"),
        Index("ix_gst_einvoices_invoice_id", "invoice_id", unique=True),
        Index("ix_gst_einvoices_irn", "irn", unique=True),
        Index("ix_gst_einvoices_status", "status"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("sales_invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    irn: Mapped[str] = mapped_column(String(100), nullable=False)
    ack_number: Mapped[str] = mapped_column(String(50), nullable=False)
    ack_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    status: Mapped[EInvoiceStatus] = mapped_column(
        Enum(EInvoiceStatus, name="e_invoice_status"),
        default=EInvoiceStatus.GENERATED,
        nullable=False,
    )
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    business: Mapped[Business] = relationship()
    invoice: Mapped[SalesInvoice] = relationship()


class EInvoiceQRCode(BaseEntity):
    """QR code data associated with an e-invoice."""

    __tablename__ = "gst_einvoice_qr_codes"
    __table_args__ = (
        Index("ix_gst_einvoice_qr_codes_invoice_id", "invoice_id", unique=True),
        Index("ix_gst_einvoice_qr_codes_hash_value", "hash_value", unique=True),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("sales_invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    qr_content: Mapped[str] = mapped_column(Text, nullable=False)
    hash_value: Mapped[str] = mapped_column(String(128), nullable=False)

    invoice: Mapped[SalesInvoice] = relationship()
