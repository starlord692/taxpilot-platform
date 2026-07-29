"""Assistant conversation model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.modules.assistant.models.enums import ConversationStatus

if TYPE_CHECKING:
    from app.modules.assistant.models.message import AssistantMessage
    from app.modules.assistant.models.run import AssistantRun


class AssistantConversation(BaseEntity):
    """Conversation-scoped assistant memory for a business user."""

    __tablename__ = "assistant_conversations"
    __table_args__ = (
        Index("ix_assistant_conversations_business_id", "business_id"),
        Index("ix_assistant_conversations_user_id", "user_id"),
        Index("ix_assistant_conversations_status", "status"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    language: Mapped[str] = mapped_column(String(16), default="en", nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(80),
        default="Asia/Calcutta",
        nullable=False,
    )
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus, name="assistant_conversation_status"),
        default=ConversationStatus.ACTIVE,
        nullable=False,
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    messages: Mapped[list[AssistantMessage]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    runs: Mapped[list[AssistantRun]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
