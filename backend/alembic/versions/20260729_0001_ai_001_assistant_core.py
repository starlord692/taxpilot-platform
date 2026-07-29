"""Add assistant core orchestration tables.

Revision ID: 20260729_0001_ai_001_assistant_core
Revises: 20260726_0001_rc1_baseline

"""

# ruff: noqa: E501, I001

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260729_0001_ai_001_assistant_core"
down_revision: str | None = "20260726_0001_rc1_baseline"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create assistant orchestration tables."""
    conversation_status = postgresql.ENUM(
        "ACTIVE",
        "ARCHIVED",
        name="assistant_conversation_status",
    )
    message_role = postgresql.ENUM(
        "USER",
        "ASSISTANT",
        "SYSTEM",
        "TOOL",
        name="assistant_message_role",
    )
    run_status = postgresql.ENUM(
        "RUNNING",
        "COMPLETED",
        "FAILED",
        name="assistant_run_status",
    )
    tool_call_status = postgresql.ENUM(
        "PENDING",
        "COMPLETED",
        "FAILED",
        name="assistant_tool_call_status",
    )
    tool_side_effect = postgresql.ENUM(
        "READ",
        "WRITE",
        name="assistant_tool_side_effect",
    )
    conversation_status.create(op.get_bind(), checkfirst=True)
    message_role.create(op.get_bind(), checkfirst=True)
    run_status.create(op.get_bind(), checkfirst=True)
    tool_call_status.create(op.get_bind(), checkfirst=True)
    tool_side_effect.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "assistant_conversations",
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("status", conversation_status, nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assistant_conversations_business_id", "assistant_conversations", ["business_id"])
    op.create_index("ix_assistant_conversations_status", "assistant_conversations", ["status"])
    op.create_index("ix_assistant_conversations_user_id", "assistant_conversations", ["user_id"])

    op.create_table(
        "assistant_messages",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("role", message_role, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
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
    op.create_index("ix_assistant_messages_conversation_id", "assistant_messages", ["conversation_id"])
    op.create_index("ix_assistant_messages_created_at", "assistant_messages", ["created_at"])
    op.create_index("ix_assistant_messages_role", "assistant_messages", ["role"])

    op.create_table(
        "assistant_runs",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("user_message_id", sa.UUID(), nullable=True),
        sa.Column("status", run_status, nullable=False),
        sa.Column("intent", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        sa.Column("provider_name", sa.String(length=80), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["assistant_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_message_id"], ["assistant_messages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assistant_runs_conversation_id", "assistant_runs", ["conversation_id"])
    op.create_index("ix_assistant_runs_prompt_version", "assistant_runs", ["prompt_version"])
    op.create_index("ix_assistant_runs_status", "assistant_runs", ["status"])

    op.create_table(
        "assistant_tool_calls",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("tool_name", sa.String(length=120), nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("output_payload", sa.JSON(), nullable=True),
        sa.Column("status", tool_call_status, nullable=False),
        sa.Column("required_business_context", sa.Boolean(), nullable=False),
        sa.Column("side_effect", tool_side_effect, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["assistant_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assistant_tool_calls_run_id", "assistant_tool_calls", ["run_id"])
    op.create_index("ix_assistant_tool_calls_status", "assistant_tool_calls", ["status"])
    op.create_index("ix_assistant_tool_calls_tool_name", "assistant_tool_calls", ["tool_name"])


def downgrade() -> None:
    """Drop assistant orchestration tables."""
    op.drop_index("ix_assistant_tool_calls_tool_name", table_name="assistant_tool_calls")
    op.drop_index("ix_assistant_tool_calls_status", table_name="assistant_tool_calls")
    op.drop_index("ix_assistant_tool_calls_run_id", table_name="assistant_tool_calls")
    op.drop_table("assistant_tool_calls")
    op.drop_index("ix_assistant_runs_status", table_name="assistant_runs")
    op.drop_index("ix_assistant_runs_prompt_version", table_name="assistant_runs")
    op.drop_index("ix_assistant_runs_conversation_id", table_name="assistant_runs")
    op.drop_table("assistant_runs")
    op.drop_index("ix_assistant_messages_role", table_name="assistant_messages")
    op.drop_index("ix_assistant_messages_created_at", table_name="assistant_messages")
    op.drop_index("ix_assistant_messages_conversation_id", table_name="assistant_messages")
    op.drop_table("assistant_messages")
    op.drop_index("ix_assistant_conversations_user_id", table_name="assistant_conversations")
    op.drop_index("ix_assistant_conversations_status", table_name="assistant_conversations")
    op.drop_index("ix_assistant_conversations_business_id", table_name="assistant_conversations")
    op.drop_table("assistant_conversations")
    op.execute("DROP TYPE IF EXISTS assistant_tool_side_effect")
    op.execute("DROP TYPE IF EXISTS assistant_tool_call_status")
    op.execute("DROP TYPE IF EXISTS assistant_run_status")
    op.execute("DROP TYPE IF EXISTS assistant_message_role")
    op.execute("DROP TYPE IF EXISTS assistant_conversation_status")




