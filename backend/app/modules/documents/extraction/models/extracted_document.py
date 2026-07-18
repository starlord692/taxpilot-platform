"""Extracted document model."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.modules.documents.extraction.models.enums import ExtractionRunStatus
from app.modules.documents.models import DocumentType

if TYPE_CHECKING:
    from app.modules.documents.extraction.models.field import ExtractedField
    from app.modules.documents.extraction.models.review import ExtractionReview
    from app.modules.documents.models import Document


class ExtractedDocument(BaseEntity):
    """Structured extraction summary for one document."""

    __tablename__ = "extracted_documents"
    __table_args__ = (
        UniqueConstraint("document_id", name="uq_extracted_documents_document_id"),
        Index("ix_extracted_documents_business_id", "business_id"),
        Index("ix_extracted_documents_document_id", "document_id"),
        Index("ix_extracted_documents_status", "status"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="extracted_document_type"),
        default=DocumentType.UNKNOWN,
        nullable=False,
    )
    overall_confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )
    status: Mapped[ExtractionRunStatus] = mapped_column(
        Enum(ExtractionRunStatus, name="document_extraction_run_status"),
        nullable=False,
    )
    review_required: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    document: Mapped[Document] = relationship()
    fields: Mapped[list[ExtractedField]] = relationship(
        back_populates="extracted_document",
        cascade="all, delete-orphan",
    )
    reviews: Mapped[list[ExtractionReview]] = relationship(
        back_populates="extracted_document",
        cascade="all, delete-orphan",
    )
