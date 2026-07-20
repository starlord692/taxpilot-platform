"""Business and financial-year scoped invoice number sequence."""

import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models.abstract import BaseEntity


class InvoiceNumberSequence(BaseEntity):
    __tablename__ = "sales_invoice_number_sequences"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "financial_year",
            name="uq_sales_invoice_sequence_business_year",
        ),
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    financial_year: Mapped[str] = mapped_column(String(9), nullable=False)
    prefix: Mapped[str] = mapped_column(String(20), nullable=False, default="INV")
    next_value: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
