"""Conversation-scoped assistant workflow model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models.abstract import BaseEntity
from app.common.models.abstract.timestamp import utc_now
from app.modules.assistant.models.enums import (
    AssistantWorkflowStatus,
    AssistantWorkflowType,
)


class AssistantWorkflow(BaseEntity):
    """Assistant workflow tracker state scoped to one conversation."""

    __tablename__ = "assistant_workflows"
    __table_args__ = (
        Index("ix_assistant_workflows_conversation_id", "conversation_id"),
        Index("ix_assistant_workflows_business_id", "business_id"),
        Index("ix_assistant_workflows_user_id", "user_id"),
        Index("ix_assistant_workflows_status", "status"),
        Index("ix_assistant_workflows_workflow_type", "workflow_type"),
        Index("ix_assistant_workflows_expires_at", "expires_at"),
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
    workflow_type: Mapped[AssistantWorkflowType] = mapped_column(
        Enum(AssistantWorkflowType, name="assistant_workflow_type"),
        nullable=False,
    )
    status: Mapped[AssistantWorkflowStatus] = mapped_column(
        Enum(AssistantWorkflowStatus, name="assistant_workflow_status"),
        nullable=False,
    )
    current_step: Mapped[str] = mapped_column(String(120), nullable=False)
    active_entity_refs: Mapped[list[dict[str, object]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    pending_decisions: Mapped[list[dict[str, object]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    provenance: Mapped[dict[str, object]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    last_transition_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
