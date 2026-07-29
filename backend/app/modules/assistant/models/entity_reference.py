"""Conversation-scoped assistant entity reference model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models.abstract import BaseEntity
from app.common.models.abstract.timestamp import utc_now
from app.modules.assistant.models.enums import (
    ContextSource,
    EntityReferenceStatus,
    EntityResolutionConfidence,
)


class AssistantEntityReference(BaseEntity):
    """Conversation-local reference to a business entity with provenance."""

    __tablename__ = "assistant_entity_references"
    __table_args__ = (
        Index("ix_assistant_entity_references_conversation_id", "conversation_id"),
        Index("ix_assistant_entity_references_business_id", "business_id"),
        Index("ix_assistant_entity_references_user_id", "user_id"),
        Index("ix_assistant_entity_references_entity_type", "entity_type"),
        Index("ix_assistant_entity_references_status", "status"),
        Index("ix_assistant_entity_references_expires_at", "expires_at"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("assistant_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        nullable=True,
    )
    entity_label: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[ContextSource] = mapped_column(
        Enum(ContextSource, name="assistant_context_source"),
        nullable=False,
    )
    confidence: Mapped[EntityResolutionConfidence] = mapped_column(
        Enum(
            EntityResolutionConfidence,
            name="assistant_entity_resolution_confidence",
        ),
        nullable=False,
    )
    confidence_score: Mapped[float] = mapped_column(
        Numeric(5, 4),
        default=0,
        nullable=False,
    )
    status: Mapped[EntityReferenceStatus] = mapped_column(
        Enum(EntityReferenceStatus, name="assistant_entity_reference_status"),
        default=EntityReferenceStatus.ACTIVE,
        nullable=False,
    )
    provenance: Mapped[dict[str, object]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
