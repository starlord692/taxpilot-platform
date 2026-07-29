"""Add assistant intelligent tool orchestration tables.

Revision ID: 20260729_0003_ai_003_tool_orchestration
Revises: 20260729_0002_ai_002_business_memory_context

"""

# ruff: noqa: E501, I001

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260729_0003_ai_003_tool_orchestration"
down_revision: str | None = "20260729_0002_ai_002_business_memory_context"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create assistant execution orchestration tables."""
    plan_status = postgresql.ENUM(
        "PLANNED",
        "APPROVAL_REQUIRED",
        "EXECUTING",
        "COMPLETED",
        "FAILED",
        "BLOCKED",
        name="assistant_execution_plan_status",
    )
    step_status = postgresql.ENUM(
        "PENDING",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "SKIPPED",
        "BLOCKED",
        name="assistant_execution_step_status",
    )
    execution_mode = postgresql.ENUM(
        "SINGLE",
        "SEQUENTIAL",
        "PARALLEL_READ_ONLY",
        name="assistant_execution_mode",
    )
    policy_decision = postgresql.ENUM(
        "ALLOWED",
        "BLOCKED",
        "REQUIRES_APPROVAL",
        "REQUIRES_CLARIFICATION",
        name="assistant_execution_policy_decision",
    )
    approval_level = postgresql.ENUM(
        "NONE",
        "AUTO_ALLOWED",
        "EXPLICIT_USER_APPROVAL",
        "ORGANIZATIONAL_APPROVAL",
        "BLOCKED",
        name="assistant_approval_level",
    )
    approval_status = postgresql.ENUM(
        "NOT_REQUIRED",
        "PENDING",
        "APPROVED",
        "REJECTED",
        "EXPIRED",
        "CANCELLED",
        name="assistant_approval_status",
    )
    plan_status.create(op.get_bind(), checkfirst=True)
    step_status.create(op.get_bind(), checkfirst=True)
    execution_mode.create(op.get_bind(), checkfirst=True)
    policy_decision.create(op.get_bind(), checkfirst=True)
    approval_level.create(op.get_bind(), checkfirst=True)
    approval_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "assistant_execution_plans",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("plan_version", sa.String(length=60), nullable=False),
        sa.Column("planner_version", sa.String(length=60), nullable=False),
        sa.Column("normalization_version", sa.String(length=60), nullable=False),
        sa.Column("prompt_version", sa.String(length=60), nullable=False),
        sa.Column("context_version", sa.String(length=60), nullable=False),
        sa.Column("status", plan_status, nullable=False),
        sa.Column("execution_mode", execution_mode, nullable=False),
        sa.Column("policy_decision", policy_decision, nullable=False),
        sa.Column("approval_level", approval_level, nullable=False),
        sa.Column("approval_status", approval_status, nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("normalized_plan", sa.JSON(), nullable=False),
        sa.Column("policy_reasons", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("correlation_id", sa.String(length=80), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["assistant_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["assistant_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "idempotency_key", name="uq_assistant_execution_plans_business_idempotency"),
    )
    op.create_index("ix_assistant_execution_plans_business_id", "assistant_execution_plans", ["business_id"])
    op.create_index("ix_assistant_execution_plans_conversation_id", "assistant_execution_plans", ["conversation_id"])
    op.create_index("ix_assistant_execution_plans_idempotency_key", "assistant_execution_plans", ["idempotency_key"])
    op.create_index("ix_assistant_execution_plans_run_id", "assistant_execution_plans", ["run_id"])
    op.create_index("ix_assistant_execution_plans_status", "assistant_execution_plans", ["status"])

    op.create_table(
        "assistant_execution_steps",
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("tool_call_id", sa.UUID(), nullable=True),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=120), nullable=False),
        sa.Column("capability_name", sa.String(length=120), nullable=False),
        sa.Column("tool_manifest_version", sa.String(length=60), nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("output_payload", sa.JSON(), nullable=True),
        sa.Column("status", step_status, nullable=False),
        sa.Column("required_business_context", sa.Boolean(), nullable=False),
        sa.Column("side_effect", postgresql.ENUM(name="assistant_tool_side_effect", create_type=False), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("dependencies", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["assistant_execution_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tool_call_id"], ["assistant_tool_calls.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "idempotency_key", name="uq_assistant_execution_steps_plan_idempotency"),
        sa.UniqueConstraint("plan_id", "step_order", name="uq_assistant_execution_steps_plan_order"),
    )
    op.create_index("ix_assistant_execution_steps_idempotency_key", "assistant_execution_steps", ["idempotency_key"])
    op.create_index("ix_assistant_execution_steps_plan_id", "assistant_execution_steps", ["plan_id"])
    op.create_index("ix_assistant_execution_steps_status", "assistant_execution_steps", ["status"])
    op.create_index("ix_assistant_execution_steps_tool_name", "assistant_execution_steps", ["tool_name"])

    op.create_table(
        "assistant_approvals",
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("requested_by", sa.UUID(), nullable=False),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        sa.Column("approval_level", approval_level, nullable=False),
        sa.Column("status", approval_status, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("plan_hash", sa.String(length=128), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["assistant_execution_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assistant_approvals_business_id", "assistant_approvals", ["business_id"])
    op.create_index("ix_assistant_approvals_expires_at", "assistant_approvals", ["expires_at"])
    op.create_index("ix_assistant_approvals_plan_id", "assistant_approvals", ["plan_id"])
    op.create_index("ix_assistant_approvals_status", "assistant_approvals", ["status"])


def downgrade() -> None:
    """Drop assistant execution orchestration tables."""
    op.drop_index("ix_assistant_approvals_status", table_name="assistant_approvals")
    op.drop_index("ix_assistant_approvals_plan_id", table_name="assistant_approvals")
    op.drop_index("ix_assistant_approvals_expires_at", table_name="assistant_approvals")
    op.drop_index("ix_assistant_approvals_business_id", table_name="assistant_approvals")
    op.drop_table("assistant_approvals")
    op.drop_index("ix_assistant_execution_steps_tool_name", table_name="assistant_execution_steps")
    op.drop_index("ix_assistant_execution_steps_status", table_name="assistant_execution_steps")
    op.drop_index("ix_assistant_execution_steps_plan_id", table_name="assistant_execution_steps")
    op.drop_index("ix_assistant_execution_steps_idempotency_key", table_name="assistant_execution_steps")
    op.drop_table("assistant_execution_steps")
    op.drop_index("ix_assistant_execution_plans_status", table_name="assistant_execution_plans")
    op.drop_index("ix_assistant_execution_plans_run_id", table_name="assistant_execution_plans")
    op.drop_index("ix_assistant_execution_plans_idempotency_key", table_name="assistant_execution_plans")
    op.drop_index("ix_assistant_execution_plans_conversation_id", table_name="assistant_execution_plans")
    op.drop_index("ix_assistant_execution_plans_business_id", table_name="assistant_execution_plans")
    op.drop_table("assistant_execution_plans")
    op.execute("DROP TYPE IF EXISTS assistant_approval_status")
    op.execute("DROP TYPE IF EXISTS assistant_approval_level")
    op.execute("DROP TYPE IF EXISTS assistant_execution_policy_decision")
    op.execute("DROP TYPE IF EXISTS assistant_execution_mode")
    op.execute("DROP TYPE IF EXISTS assistant_execution_step_status")
    op.execute("DROP TYPE IF EXISTS assistant_execution_plan_status")
