"""Add assistant business memory and context intelligence tables.

Revision ID: 20260729_0002_ai_002_business_memory_context
Revises: 20260729_0001_ai_001_assistant_core

"""

# ruff: noqa: E501, I001

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260729_0002_ai_002_business_memory_context"
down_revision: str | None = "20260729_0001_ai_001_assistant_core"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create assistant context intelligence tables."""
    context_type = postgresql.ENUM("RUN", "SUMMARY", "WORKFLOW", name="assistant_context_type")
    context_source = postgresql.ENUM("USER_MESSAGE", "TOOL_OUTPUT", "SYSTEM_DERIVED", "BUSINESS_CONTEXT", name="assistant_context_source")
    entity_reference_status = postgresql.ENUM("ACTIVE", "EXPIRED", "REPLACED", name="assistant_entity_reference_status")
    entity_confidence = postgresql.ENUM("HIGH", "MEDIUM", "LOW", "AMBIGUOUS", "UNRESOLVED", name="assistant_entity_resolution_confidence")
    workflow_status = postgresql.ENUM("NOT_STARTED", "ACTIVE", "WAITING_FOR_USER", "EXECUTING_TOOLS", "READY_FOR_ACTION", "COMPLETED", "INTERRUPTED", "EXPIRED", "FAILED", name="assistant_workflow_status")
    workflow_type = postgresql.ENUM("GENERAL", "SALES_INVOICE", "PURCHASE_INVOICE", "EXPENSE_REVIEW", "GST_REVIEW", "INVENTORY_CHECK", "DOCUMENT_REVIEW", "ACCOUNTING_REPORT", name="assistant_workflow_type")
    context_type.create(op.get_bind(), checkfirst=True)
    context_source.create(op.get_bind(), checkfirst=True)
    entity_reference_status.create(op.get_bind(), checkfirst=True)
    entity_confidence.create(op.get_bind(), checkfirst=True)
    workflow_status.create(op.get_bind(), checkfirst=True)
    workflow_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "assistant_context_snapshots",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("context_version", sa.String(length=40), nullable=False),
        sa.Column("context_type", context_type, nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["assistant_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assistant_context_snapshots_business_id", "assistant_context_snapshots", ["business_id"])
    op.create_index("ix_assistant_context_snapshots_context_type", "assistant_context_snapshots", ["context_type"])
    op.create_index("ix_assistant_context_snapshots_conversation_id", "assistant_context_snapshots", ["conversation_id"])
    op.create_index("ix_assistant_context_snapshots_expires_at", "assistant_context_snapshots", ["expires_at"])
    op.create_index("ix_assistant_context_snapshots_user_id", "assistant_context_snapshots", ["user_id"])

    op.create_table(
        "assistant_entity_references",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column("entity_label", sa.String(length=255), nullable=False),
        sa.Column("source", context_source, nullable=False),
        sa.Column("confidence", entity_confidence, nullable=False),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("status", entity_reference_status, nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["assistant_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assistant_entity_references_business_id", "assistant_entity_references", ["business_id"])
    op.create_index("ix_assistant_entity_references_conversation_id", "assistant_entity_references", ["conversation_id"])
    op.create_index("ix_assistant_entity_references_entity_type", "assistant_entity_references", ["entity_type"])
    op.create_index("ix_assistant_entity_references_expires_at", "assistant_entity_references", ["expires_at"])
    op.create_index("ix_assistant_entity_references_status", "assistant_entity_references", ["status"])
    op.create_index("ix_assistant_entity_references_user_id", "assistant_entity_references", ["user_id"])

    op.create_table(
        "assistant_workflows",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("workflow_type", workflow_type, nullable=False),
        sa.Column("status", workflow_status, nullable=False),
        sa.Column("current_step", sa.String(length=120), nullable=False),
        sa.Column("active_entity_refs", sa.JSON(), nullable=False),
        sa.Column("pending_decisions", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_transition_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["assistant_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assistant_workflows_business_id", "assistant_workflows", ["business_id"])
    op.create_index("ix_assistant_workflows_conversation_id", "assistant_workflows", ["conversation_id"])
    op.create_index("ix_assistant_workflows_expires_at", "assistant_workflows", ["expires_at"])
    op.create_index("ix_assistant_workflows_status", "assistant_workflows", ["status"])
    op.create_index("ix_assistant_workflows_user_id", "assistant_workflows", ["user_id"])
    op.create_index("ix_assistant_workflows_workflow_type", "assistant_workflows", ["workflow_type"])


def downgrade() -> None:
    """Drop assistant context intelligence tables."""
    op.drop_index("ix_assistant_workflows_workflow_type", table_name="assistant_workflows")
    op.drop_index("ix_assistant_workflows_user_id", table_name="assistant_workflows")
    op.drop_index("ix_assistant_workflows_status", table_name="assistant_workflows")
    op.drop_index("ix_assistant_workflows_expires_at", table_name="assistant_workflows")
    op.drop_index("ix_assistant_workflows_conversation_id", table_name="assistant_workflows")
    op.drop_index("ix_assistant_workflows_business_id", table_name="assistant_workflows")
    op.drop_table("assistant_workflows")
    op.drop_index("ix_assistant_entity_references_user_id", table_name="assistant_entity_references")
    op.drop_index("ix_assistant_entity_references_status", table_name="assistant_entity_references")
    op.drop_index("ix_assistant_entity_references_expires_at", table_name="assistant_entity_references")
    op.drop_index("ix_assistant_entity_references_entity_type", table_name="assistant_entity_references")
    op.drop_index("ix_assistant_entity_references_conversation_id", table_name="assistant_entity_references")
    op.drop_index("ix_assistant_entity_references_business_id", table_name="assistant_entity_references")
    op.drop_table("assistant_entity_references")
    op.drop_index("ix_assistant_context_snapshots_user_id", table_name="assistant_context_snapshots")
    op.drop_index("ix_assistant_context_snapshots_expires_at", table_name="assistant_context_snapshots")
    op.drop_index("ix_assistant_context_snapshots_conversation_id", table_name="assistant_context_snapshots")
    op.drop_index("ix_assistant_context_snapshots_context_type", table_name="assistant_context_snapshots")
    op.drop_index("ix_assistant_context_snapshots_business_id", table_name="assistant_context_snapshots")
    op.drop_table("assistant_context_snapshots")
    op.execute("DROP TYPE IF EXISTS assistant_workflow_type")
    op.execute("DROP TYPE IF EXISTS assistant_workflow_status")
    op.execute("DROP TYPE IF EXISTS assistant_entity_resolution_confidence")
    op.execute("DROP TYPE IF EXISTS assistant_entity_reference_status")
    op.execute("DROP TYPE IF EXISTS assistant_context_source")
    op.execute("DROP TYPE IF EXISTS assistant_context_type")
