"""Validation issue model."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.modules.documents.review.models.enums import (
    ValidationCategory,
    ValidationSeverity,
)


class ValidationIssue(BaseEntity):
    """Business validation issue for extracted document data."""

    __tablename__ = "document_validation_issues"
    __table_args__ = (
        Index("ix_document_validation_issues_document_id", "document_id"),
        Index("ix_document_validation_issues_severity", "severity"),
        Index("ix_document_validation_issues_category", "category"),
        Index("ix_document_validation_issues_resolved", "resolved"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    severity: Mapped[ValidationSeverity] = mapped_column(
        Enum(ValidationSeverity, name="document_validation_severity"),
        nullable=False,
    )
    category: Mapped[ValidationCategory] = mapped_column(
        Enum(ValidationCategory, name="document_validation_category"),
        nullable=False,
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    expected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    document = relationship("Document")
