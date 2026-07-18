"""Automation run model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.modules.documents.automation.models.enums import (
    AutomationState,
    AutomationType,
)


class AutomationRun(BaseEntity):
    """Audit and idempotency record for document ERP automation."""

    __tablename__ = "document_automation_runs"
    __table_args__ = (
        Index("ix_document_automation_runs_document_id", "document_id"),
        Index("ix_document_automation_runs_business_id", "business_id"),
        Index(
            "ix_document_automation_runs_idempotency_key",
            "idempotency_key",
            unique=True,
        ),
        Index("ix_document_automation_runs_status", "status"),
        Index(
            "ix_document_automation_runs_erp_record",
            "erp_record_type",
            "erp_record_id",
        ),
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
    automation_type: Mapped[AutomationType] = mapped_column(
        Enum(AutomationType, name="document_automation_type"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[AutomationState] = mapped_column(
        Enum(AutomationState, name="document_automation_state"),
        default=AutomationState.NOT_STARTED,
        nullable=False,
    )
    erp_record_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    erp_record_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    document = relationship("Document")
    business = relationship("Business")
