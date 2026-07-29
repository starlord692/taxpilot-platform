"""Assistant execution step audit model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.modules.assistant.models.enums import ExecutionStepStatus, ToolSideEffect

if TYPE_CHECKING:
    from app.modules.assistant.models.execution_plan import AssistantExecutionPlan


class AssistantExecutionStep(BaseEntity):
    """Auditable step inside an assistant execution plan."""

    __tablename__ = "assistant_execution_steps"
    __table_args__ = (
        Index("ix_assistant_execution_steps_plan_id", "plan_id"),
        Index("ix_assistant_execution_steps_status", "status"),
        Index("ix_assistant_execution_steps_tool_name", "tool_name"),
        Index("ix_assistant_execution_steps_idempotency_key", "idempotency_key"),
        UniqueConstraint(
            "plan_id",
            "step_order",
            name="uq_assistant_execution_steps_plan_order",
        ),
        UniqueConstraint(
            "plan_id",
            "idempotency_key",
            name="uq_assistant_execution_steps_plan_idempotency",
        ),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("assistant_execution_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    tool_call_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("assistant_tool_calls.id", ondelete="SET NULL"),
        nullable=True,
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(120), nullable=False)
    capability_name: Mapped[str] = mapped_column(String(120), nullable=False)
    tool_manifest_version: Mapped[str] = mapped_column(String(60), nullable=False)
    input_payload: Mapped[dict[str, object]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    output_payload: Mapped[dict[str, object] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    status: Mapped[ExecutionStepStatus] = mapped_column(
        Enum(ExecutionStepStatus, name="assistant_execution_step_status"),
        default=ExecutionStepStatus.PENDING,
        nullable=False,
    )
    required_business_context: Mapped[bool] = mapped_column(nullable=False)
    side_effect: Mapped[ToolSideEffect] = mapped_column(
        Enum(ToolSideEffect, name="assistant_tool_side_effect"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    dependencies: Mapped[list[object]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    provenance: Mapped[dict[str, object]] = mapped_column(
        JSON,
        default=dict,
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
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    plan: Mapped[AssistantExecutionPlan] = relationship(back_populates="steps")


