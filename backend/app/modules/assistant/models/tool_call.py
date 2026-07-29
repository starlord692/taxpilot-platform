"""Assistant tool-call audit model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.modules.assistant.models.enums import ToolCallStatus, ToolSideEffect

if TYPE_CHECKING:
    from app.modules.assistant.models.run import AssistantRun


class AssistantToolCall(BaseEntity):
    """Audited execution record for an assistant tool call."""

    __tablename__ = "assistant_tool_calls"
    __table_args__ = (
        Index("ix_assistant_tool_calls_run_id", "run_id"),
        Index("ix_assistant_tool_calls_tool_name", "tool_name"),
        Index("ix_assistant_tool_calls_status", "status"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("assistant_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    tool_name: Mapped[str] = mapped_column(String(120), nullable=False)
    input_payload: Mapped[dict[str, object]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    output_payload: Mapped[dict[str, object] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    status: Mapped[ToolCallStatus] = mapped_column(
        Enum(ToolCallStatus, name="assistant_tool_call_status"),
        default=ToolCallStatus.PENDING,
        nullable=False,
    )
    required_business_context: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    side_effect: Mapped[ToolSideEffect] = mapped_column(
        Enum(ToolSideEffect, name="assistant_tool_side_effect"),
        default=ToolSideEffect.READ,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)

    run: Mapped[AssistantRun] = relationship(back_populates="tool_calls")
