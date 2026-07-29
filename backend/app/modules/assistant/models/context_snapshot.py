"""Conversation-scoped assistant context snapshot model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models.abstract import BaseEntity
from app.common.models.abstract.timestamp import utc_now
from app.modules.assistant.models.enums import ContextType


class AssistantContextSnapshot(BaseEntity):
    """Auditable context snapshot generated for one assistant conversation run."""

    __tablename__ = "assistant_context_snapshots"
    __table_args__ = (
        Index("ix_assistant_context_snapshots_conversation_id", "conversation_id"),
        Index("ix_assistant_context_snapshots_business_id", "business_id"),
        Index("ix_assistant_context_snapshots_user_id", "user_id"),
        Index("ix_assistant_context_snapshots_context_type", "context_type"),
        Index("ix_assistant_context_snapshots_expires_at", "expires_at"),
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
    context_version: Mapped[str] = mapped_column(String(40), nullable=False)
    context_type: Mapped[ContextType] = mapped_column(
        Enum(ContextType, name="assistant_context_type"),
        nullable=False,
    )
    payload: Mapped[dict[str, object]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    provenance: Mapped[dict[str, object]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
