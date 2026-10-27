"""SQLAlchemy model for persistent GSTIN verification evidence.

Governed under TAX-01 / FD-TAX-01-05.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.modules.gst.evidence import GSTINEvidenceStatus, GSTINVerificationEvidence

if TYPE_CHECKING:
    from app.modules.business.models import Business
    from app.modules.sales.models.customer import Customer


class GSTINVerification(BaseEntity):
    """Authoritative tenant-scoped persistent GSTIN verification evidence record."""

    __tablename__ = "gstin_verifications"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "gstin",
            name="uq_gstin_verifications_business_gstin",
        ),
        Index("ix_gstin_verifications_business_id", "business_id"),
        Index("ix_gstin_verifications_gstin", "gstin"),
        Index("ix_gstin_verifications_status", "status"),
        Index("ix_gstin_verifications_customer_id", "customer_id"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
    )
    gstin: Mapped[str] = mapped_column(String(15), nullable=False)
    status: Mapped[GSTINEvidenceStatus] = mapped_column(
        Enum(GSTINEvidenceStatus, name="gstin_evidence_status"),
        default=GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED,
        nullable=False,
    )
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trade_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    registration_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    evidence_source: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    raw_payload_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    evidence_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        default=dict,
        nullable=True,
    )

    business: Mapped[Business] = relationship()
    customer: Mapped[Customer | None] = relationship()

    def to_evidence_record(self) -> GSTINVerificationEvidence:
        """Convert persistent model to domain evidence value object."""
        return GSTINVerificationEvidence(
            gstin=self.gstin,
            status=self.status,
            evidence_source=self.evidence_source,
            verified_at=self.verified_at,
            evidence_metadata=self.evidence_metadata or {},
        )
