"""Extraction review model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity

if TYPE_CHECKING:
    from app.modules.documents.extraction.models.extracted_document import (
        ExtractedDocument,
    )


class ExtractionReview(BaseEntity):
    """Review metadata for low-confidence or invalid extraction output."""

    __tablename__ = "extraction_reviews"
    __table_args__ = (
        Index("ix_extraction_reviews_extracted_document_id", "extracted_document_id"),
        Index("ix_extraction_reviews_resolved", "resolved"),
    )

    extracted_document_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("extracted_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    extracted_document: Mapped[ExtractedDocument] = relationship(
        back_populates="reviews",
    )
