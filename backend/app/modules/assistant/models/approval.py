"""Assistant approval checkpoint audit model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.modules.assistant.models.enums import ApprovalLevel, ApprovalStatus

if TYPE_CHECKING:
    from app.modules.assistant.models.execution_plan import AssistantExecutionPlan


class AssistantApproval(BaseEntity):
    """Approval checkpoint for consequential assistant execution plans."""

    __tablename__ = "assistant_approvals"
    __table_args__ = (
        Index("ix_assistant_approvals_plan_id", "plan_id"),
        Index("ix_assistant_approvals_business_id", "business_id"),
        Index("ix_assistant_approvals_status", "status"),
        Index("ix_assistant_approvals_expires_at", "expires_at"),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("assistant_execution_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        nullable=False,
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        nullable=False,
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        nullable=True,
    )
    approval_level: Mapped[ApprovalLevel] = mapped_column(
        Enum(ApprovalLevel, name="assistant_approval_level"),
        nullable=False,
    )
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, name="assistant_approval_status"),
        default=ApprovalStatus.PENDING,
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    plan_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    provenance: Mapped[dict[str, object]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    plan: Mapped[AssistantExecutionPlan] = relationship(back_populates="approvals")
