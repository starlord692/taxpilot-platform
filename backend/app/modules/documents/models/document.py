"""Document metadata model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.common.models.abstract.timestamp import utc_now
from app.modules.documents.models.enums import DocumentType, ExtractionStatus

if TYPE_CHECKING:
    from app.modules.business.models import Business
    from app.modules.documents.models.ocr_result import OCRResult
    from app.modules.documents.models.page import DocumentPage
    from app.modules.identity.models import IdentityUser


class Document(BaseEntity):
    """Uploaded document metadata and processing state."""

    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_business_id", "business_id"),
        Index("ix_documents_uploaded_by", "uploaded_by"),
        Index("ix_documents_checksum", "checksum"),
        Index("ix_documents_document_type", "document_type"),
        Index("ix_documents_status", "status"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("identity_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type"),
        default=DocumentType.UNKNOWN,
        nullable=False,
    )
    status: Mapped[ExtractionStatus] = mapped_column(
        Enum(ExtractionStatus, name="document_extraction_status"),
        default=ExtractionStatus.UPLOADED,
        nullable=False,
    )
    page_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    business: Mapped[Business] = relationship()
    uploader: Mapped[IdentityUser] = relationship()
    pages: Mapped[list[DocumentPage]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
    ocr_results: Mapped[list[OCRResult]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
