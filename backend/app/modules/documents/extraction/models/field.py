"""Extracted field model."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Enum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.modules.documents.extraction.models.enums import ExtractedFieldSource

if TYPE_CHECKING:
    from app.modules.documents.extraction.models.extracted_document import (
        ExtractedDocument,
    )
    from app.modules.documents.models import Document


class ExtractedField(BaseEntity):
    """One structured field extracted from OCR text."""

    __tablename__ = "extracted_fields"
    __table_args__ = (
        Index("ix_extracted_fields_document_id", "document_id"),
        Index("ix_extracted_fields_field_name", "field_name"),
        Index("ix_extracted_fields_source", "source"),
    )

    extracted_document_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("extracted_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    source: Mapped[ExtractedFieldSource] = mapped_column(
        Enum(ExtractedFieldSource, name="extracted_field_source"),
        nullable=False,
    )
    page_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    bounding_box: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    extracted_document: Mapped[ExtractedDocument] = relationship(
        back_populates="fields",
    )
    document: Mapped[Document] = relationship()
