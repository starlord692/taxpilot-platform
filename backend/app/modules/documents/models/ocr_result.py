"""OCR result model."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity

if TYPE_CHECKING:
    from app.modules.documents.models.document import Document


class OCRResult(BaseEntity):
    """OCR text and metadata for one document page."""

    __tablename__ = "ocr_results"
    __table_args__ = (
        Index("ix_ocr_results_document_id", "document_id"),
        Index("ix_ocr_results_provider", "provider"),
        Index("ix_ocr_results_page_number", "page_number"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )
    processing_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    document: Mapped[Document] = relationship(back_populates="ocr_results")
