"""Document review model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.modules.documents.review.models.enums import ReviewStatus


class DocumentReview(BaseEntity):
    """Human review state for a document extraction."""

    __tablename__ = "document_reviews"
    __table_args__ = (
        Index("ix_document_reviews_document_id", "document_id", unique=True),
        Index("ix_document_reviews_status", "review_status"),
        Index("ix_document_reviews_ready", "ready_for_automation"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="document_review_status"),
        default=ReviewStatus.PENDING,
        nullable=False,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("identity_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ready_for_automation: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    document = relationship("Document")
