"""Add assistant guided action draft tables.

Revision ID: 20260730_0004_ai007
Revises: 20260729_0003_ai003

"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260730_0004_ai007"
down_revision: str | None = "20260729_0003_ai003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create assistant guided action tables."""
    action_type = postgresql.ENUM(
        "SALES_INVOICE_CREATE_DRAFT",
        "PURCHASE_INVOICE_CREATE_DRAFT",
        "EXPENSE_CREATE_DRAFT",
        "VENDOR_CREATE_DRAFT",
        "PAYMENT_RECORD",
        name="assistant_action_type",
    )
    action_status = postgresql.ENUM(
        "DRAFT",
        "VALIDATION_FAILED",
        "READY_FOR_APPROVAL",
        "APPROVAL_PENDING",
        "APPROVED",
        "EXECUTING",
        "COMPLETED",
        "FAILED",
        "EXPIRED",
        "CANCELLED",
        name="assistant_action_status",
    )
    readiness_status = postgresql.ENUM(
        "READY",
        "NEEDS_APPROVAL",
        "BLOCKED",
        "INVALID",
        name="assistant_action_readiness_status",
    )
    result_status = postgresql.ENUM(
        "COMPLETED",
        "FAILED",
        "REPLAYED",
        name="assistant_action_result_status",
    )
    action_type.create(op.get_bind(), checkfirst=True)
    action_status.create(op.get_bind(), checkfirst=True)
    readiness_status.create(op.get_bind(), checkfirst=True)
    result_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "assistant_action_drafts",
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "action_type",
            postgresql.ENUM(name="assistant_action_type", create_type=False),
            nullable=False,
        ),
        sa.Column("manifest_version", sa.String(length=80), nullable=False),
        sa.Column("capability_version", sa.String(length=80), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="assistant_action_status", create_type=False),
            nullable=False,
        ),
        sa.Column("draft_payload", sa.JSON(), nullable=False),
        sa.Column("validated_payload", sa.JSON(), nullable=True),
        sa.Column(
            "readiness_status",
            postgresql.ENUM(
                name="assistant_action_readiness_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("readiness_findings", sa.JSON(), nullable=False),
        sa.Column("execution_preview", sa.JSON(), nullable=True),
        sa.Column("approval_required", sa.Boolean(), nullable=False),
        sa.Column(
            "approval_level",
            postgresql.ENUM(name="assistant_approval_level", create_type=False),
            nullable=False,
        ),
        sa.Column("approval_id", sa.UUID(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["approval_id"], ["assistant_approvals.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["assistant_conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["assistant_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "business_id",
            "idempotency_key",
            name="uq_assistant_action_drafts_business_idempotency",
        ),
    )
    op.create_index(
        "ix_assistant_action_drafts_action_type",
        "assistant_action_drafts",
        ["action_type"],
    )
    op.create_index(
        "ix_assistant_action_drafts_business_id",
        "assistant_action_drafts",
        ["business_id"],
    )
    op.create_index(
        "ix_assistant_action_drafts_conversation_id",
        "assistant_action_drafts",
        ["conversation_id"],
    )
    op.create_index(
        "ix_assistant_action_drafts_idempotency_key",
        "assistant_action_drafts",
        ["idempotency_key"],
    )
    op.create_index(
        "ix_assistant_action_drafts_run_id", "assistant_action_drafts", ["run_id"]
    )
    op.create_index(
        "ix_assistant_action_drafts_status", "assistant_action_drafts", ["status"]
    )

    op.create_table(
        "assistant_action_results",
        sa.Column("draft_id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("erp_record_type", sa.String(length=80), nullable=True),
        sa.Column("erp_record_id", sa.UUID(), nullable=True),
        sa.Column("domain_service", sa.String(length=120), nullable=False),
        sa.Column("tool_call_id", sa.UUID(), nullable=True),
        sa.Column("execution_plan_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="assistant_action_result_status", create_type=False),
            nullable=False,
        ),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["draft_id"], ["assistant_action_drafts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["execution_plan_id"], ["assistant_execution_plans.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["tool_call_id"], ["assistant_tool_calls.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_assistant_action_results_business_id",
        "assistant_action_results",
        ["business_id"],
    )
    op.create_index(
        "ix_assistant_action_results_draft_id", "assistant_action_results", ["draft_id"]
    )
    op.create_index(
        "ix_assistant_action_results_erp_record",
        "assistant_action_results",
        ["erp_record_type", "erp_record_id"],
    )
    op.create_index(
        "ix_assistant_action_results_status", "assistant_action_results", ["status"]
    )


def downgrade() -> None:
    """Drop assistant guided action tables."""
    op.drop_index(
        "ix_assistant_action_results_status", table_name="assistant_action_results"
    )
    op.drop_index(
        "ix_assistant_action_results_erp_record", table_name="assistant_action_results"
    )
    op.drop_index(
        "ix_assistant_action_results_draft_id", table_name="assistant_action_results"
    )
    op.drop_index(
        "ix_assistant_action_results_business_id", table_name="assistant_action_results"
    )
    op.drop_table("assistant_action_results")
    op.drop_index(
        "ix_assistant_action_drafts_status", table_name="assistant_action_drafts"
    )
    op.drop_index(
        "ix_assistant_action_drafts_run_id", table_name="assistant_action_drafts"
    )
    op.drop_index(
        "ix_assistant_action_drafts_idempotency_key",
        table_name="assistant_action_drafts",
    )
    op.drop_index(
        "ix_assistant_action_drafts_conversation_id",
        table_name="assistant_action_drafts",
    )
    op.drop_index(
        "ix_assistant_action_drafts_business_id", table_name="assistant_action_drafts"
    )
    op.drop_index(
        "ix_assistant_action_drafts_action_type", table_name="assistant_action_drafts"
    )
    op.drop_table("assistant_action_drafts")
    postgresql.ENUM(name="assistant_action_result_status").drop(
        op.get_bind(), checkfirst=True
    )
    postgresql.ENUM(name="assistant_action_readiness_status").drop(
        op.get_bind(), checkfirst=True
    )
    postgresql.ENUM(name="assistant_action_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="assistant_action_type").drop(op.get_bind(), checkfirst=True)


