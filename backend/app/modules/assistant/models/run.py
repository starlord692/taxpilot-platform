"""Assistant run model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.common.models.abstract.timestamp import utc_now
from app.modules.assistant.models.enums import AssistantRunStatus

if TYPE_CHECKING:
    from app.modules.assistant.models.conversation import AssistantConversation
    from app.modules.assistant.models.tool_call import AssistantToolCall


class AssistantRun(BaseEntity):
    """Auditable assistant orchestration attempt."""

    __tablename__ = "assistant_runs"
    __table_args__ = (
        Index("ix_assistant_runs_conversation_id", "conversation_id"),
        Index("ix_assistant_runs_status", "status"),
        Index("ix_assistant_runs_prompt_version", "prompt_version"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("assistant_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_message_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("assistant_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[AssistantRunStatus] = mapped_column(
        Enum(AssistantRunStatus, name="assistant_run_status"),
        default=AssistantRunStatus.RUNNING,
        nullable=False,
    )
    intent: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(80), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    conversation: Mapped[AssistantConversation] = relationship(back_populates="runs")
    tool_calls: Mapped[list[AssistantToolCall]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
