"""Assistant guided action SQLAlchemy models."""

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
from app.modules.assistant.actions.enums import (
    ActionReadinessStatus,
    AssistantActionResultStatus,
    AssistantActionStatus,
    AssistantActionType,
)
from app.modules.assistant.models import ApprovalLevel

if TYPE_CHECKING:
    from app.modules.assistant.models.approval import AssistantApproval
    from app.modules.assistant.models.conversation import AssistantConversation
    from app.modules.assistant.models.run import AssistantRun


class AssistantActionDraft(BaseEntity):
    """Draft-first assistant action record before controlled ERP execution."""

    __tablename__ = "assistant_action_drafts"
    __table_args__ = (
        Index("ix_assistant_action_drafts_business_id", "business_id"),
        Index("ix_assistant_action_drafts_conversation_id", "conversation_id"),
        Index("ix_assistant_action_drafts_run_id", "run_id"),
        Index("ix_assistant_action_drafts_action_type", "action_type"),
        Index("ix_assistant_action_drafts_status", "status"),
        Index("ix_assistant_action_drafts_idempotency_key", "idempotency_key"),
        UniqueConstraint(
            "business_id",
            "idempotency_key",
            name="uq_assistant_action_drafts_business_idempotency",
        ),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=False
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
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=False
    )
    action_type: Mapped[AssistantActionType] = mapped_column(
        Enum(AssistantActionType, name="assistant_action_type"),
        nullable=False,
    )
    manifest_version: Mapped[str] = mapped_column(String(80), nullable=False)
    capability_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[AssistantActionStatus] = mapped_column(
        Enum(AssistantActionStatus, name="assistant_action_status"),
        default=AssistantActionStatus.DRAFT,
        nullable=False,
    )
    draft_payload: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    validated_payload: Mapped[dict[str, object] | None] = mapped_column(
        JSON, nullable=True
    )
    readiness_status: Mapped[ActionReadinessStatus] = mapped_column(
        Enum(ActionReadinessStatus, name="assistant_action_readiness_status"),
        default=ActionReadinessStatus.INVALID,
        nullable=False,
    )
    readiness_findings: Mapped[list[object]] = mapped_column(
        JSON, default=list, nullable=False
    )
    execution_preview: Mapped[dict[str, object] | None] = mapped_column(
        JSON, nullable=True
    )
    approval_required: Mapped[bool] = mapped_column(default=True, nullable=False)
    approval_level: Mapped[ApprovalLevel] = mapped_column(
        Enum(ApprovalLevel, name="assistant_approval_level", create_type=False),
        default=ApprovalLevel.EXPLICIT_USER_APPROVAL,
        nullable=False,
    )
    approval_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("assistant_approvals.id", ondelete="SET NULL"),
        nullable=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    provenance: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    conversation: Mapped[AssistantConversation] = relationship()
    run: Mapped[AssistantRun] = relationship()
    approval: Mapped[AssistantApproval | None] = relationship()
    results: Mapped[list[AssistantActionResult]] = relationship(
        back_populates="draft",
        cascade="all, delete-orphan",
    )


class AssistantActionResult(BaseEntity):
    """Execution result for a controlled assistant action."""

    __tablename__ = "assistant_action_results"
    __table_args__ = (
        Index("ix_assistant_action_results_draft_id", "draft_id"),
        Index("ix_assistant_action_results_business_id", "business_id"),
        Index("ix_assistant_action_results_status", "status"),
        Index(
            "ix_assistant_action_results_erp_record", "erp_record_type", "erp_record_id"
        ),
    )

    draft_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("assistant_action_drafts.id", ondelete="CASCADE"),
        nullable=False,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=False
    )
    erp_record_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    erp_record_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=True
    )
    domain_service: Mapped[str] = mapped_column(String(120), nullable=False)
    tool_call_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("assistant_tool_calls.id", ondelete="SET NULL"),
        nullable=True,
    )
    execution_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("assistant_execution_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[AssistantActionResultStatus] = mapped_column(
        Enum(AssistantActionResultStatus, name="assistant_action_result_status"),
        nullable=False,
    )
    result_payload: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    draft: Mapped[AssistantActionDraft] = relationship(back_populates="results")

    @classmethod
    def completed(
        cls,
        *,
        draft_id: uuid.UUID,
        business_id: uuid.UUID,
        domain_service: str,
        result_payload: dict[str, object],
        erp_record_type: str | None = None,
        erp_record_id: uuid.UUID | None = None,
    ) -> AssistantActionResult:
        """Build a completed action result."""
        return cls(
            draft_id=draft_id,
            business_id=business_id,
            erp_record_type=erp_record_type,
            erp_record_id=erp_record_id,
            domain_service=domain_service,
            status=AssistantActionResultStatus.COMPLETED,
            result_payload=result_payload,
            completed_at=utc_now(),
        )
