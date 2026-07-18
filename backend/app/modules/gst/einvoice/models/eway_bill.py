"""E-way bill persistence model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.modules.gst.einvoice.models.enums import EWayBillStatus, TransportMode

if TYPE_CHECKING:
    from app.modules.sales.models import SalesInvoice


class EWayBill(BaseEntity):
    """Provider-generated e-way bill for a sales invoice."""

    __tablename__ = "gst_eway_bills"
    __table_args__ = (
        Index("ix_gst_eway_bills_invoice_id", "invoice_id", unique=True),
        Index("ix_gst_eway_bills_number", "eway_bill_number", unique=True),
        Index("ix_gst_eway_bills_status", "status"),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("sales_invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    eway_bill_number: Mapped[str] = mapped_column(String(50), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    valid_to: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    vehicle_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    transport_mode: Mapped[TransportMode] = mapped_column(
        Enum(TransportMode, name="eway_bill_transport_mode"),
        nullable=False,
    )
    status: Mapped[EWayBillStatus] = mapped_column(
        Enum(EWayBillStatus, name="eway_bill_status"),
        default=EWayBillStatus.GENERATED,
        nullable=False,
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    invoice: Mapped[SalesInvoice] = relationship()
