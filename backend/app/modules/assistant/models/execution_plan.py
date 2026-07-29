"""Assistant execution plan audit model."""

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
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.common.models.abstract.timestamp import utc_now
from app.modules.assistant.models.enums import (
    ApprovalLevel,
    ApprovalStatus,
    ExecutionMode,
    ExecutionPlanStatus,
    ExecutionPolicyDecision,
)

if TYPE_CHECKING:
    from app.modules.assistant.models.approval import AssistantApproval
    from app.modules.assistant.models.conversation import AssistantConversation
    from app.modules.assistant.models.execution_step import AssistantExecutionStep
    from app.modules.assistant.models.run import AssistantRun


class AssistantExecutionPlan(BaseEntity):
    """Versioned deterministic plan derived from provider intent."""

    __tablename__ = "assistant_execution_plans"
    __table_args__ = (
        Index("ix_assistant_execution_plans_business_id", "business_id"),
        Index("ix_assistant_execution_plans_conversation_id", "conversation_id"),
        Index("ix_assistant_execution_plans_run_id", "run_id"),
        Index("ix_assistant_execution_plans_status", "status"),
        Index("ix_assistant_execution_plans_idempotency_key", "idempotency_key"),
        UniqueConstraint(
            "business_id",
            "idempotency_key",
            name="uq_assistant_execution_plans_business_idempotency",
        ),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("assistant_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("assistant_runs.id", ondelete="CASCADE"),
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
    plan_version: Mapped[str] = mapped_column(String(60), nullable=False)
    planner_version: Mapped[str] = mapped_column(String(60), nullable=False)
    normalization_version: Mapped[str] = mapped_column(String(60), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(60), nullable=False)
    context_version: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[ExecutionPlanStatus] = mapped_column(
        Enum(ExecutionPlanStatus, name="assistant_execution_plan_status"),
        default=ExecutionPlanStatus.PLANNED,
        nullable=False,
    )
    execution_mode: Mapped[ExecutionMode] = mapped_column(
        Enum(ExecutionMode, name="assistant_execution_mode"),
        default=ExecutionMode.SINGLE,
        nullable=False,
    )
    policy_decision: Mapped[ExecutionPolicyDecision] = mapped_column(
        Enum(ExecutionPolicyDecision, name="assistant_execution_policy_decision"),
        default=ExecutionPolicyDecision.ALLOWED,
        nullable=False,
    )
    approval_level: Mapped[ApprovalLevel] = mapped_column(
        Enum(ApprovalLevel, name="assistant_approval_level"),
        default=ApprovalLevel.NONE,
        nullable=False,
    )
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, name="assistant_approval_status"),
        default=ApprovalStatus.NOT_REQUIRED,
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    normalized_plan: Mapped[dict[str, object]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    policy_reasons: Mapped[list[object]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    provenance: Mapped[dict[str, object]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    correlation_id: Mapped[str] = mapped_column(String(80), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    conversation: Mapped[AssistantConversation] = relationship()
    run: Mapped[AssistantRun] = relationship()
    steps: Mapped[list[AssistantExecutionStep]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
    )
    approvals: Mapped[list[AssistantApproval]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
    )
