"""Review decision model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.common.models.abstract.timestamp import utc_now
from app.modules.documents.review.models.enums import ReviewDecisionType


class ReviewDecision(BaseEntity):
    """Audit trail entry for review decisions."""

    __tablename__ = "document_review_decisions"
    __table_args__ = (
        Index("ix_document_review_decisions_document_id", "document_id"),
        Index("ix_document_review_decisions_decision", "decision"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    decision: Mapped[ReviewDecisionType] = mapped_column(
        Enum(ReviewDecisionType, name="document_review_decision_type"),
        nullable=False,
    )
    decided_by: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("identity_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    document = relationship("Document")
