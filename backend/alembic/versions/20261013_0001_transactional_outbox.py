"""Create transactional outbox events table."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261013_0001"
down_revision: str | None = "20260913_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create outbox_events table."""
    uuid_type = postgresql.UUID(as_uuid=True)

    def common_columns() -> list[sa.Column[object]]:
        return [
            sa.Column("id", uuid_type, primary_key=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", uuid_type, nullable=True),
            sa.Column("updated_by", uuid_type, nullable=True),
            sa.Column(
                "is_deleted",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        ]

    op.create_table(
        "outbox_events",
        *common_columns(),
        sa.Column(
            "business_id",
            uuid_type,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("event_name", sa.String(120), nullable=False),
        sa.Column("event_payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_by", sa.String(100), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'PUBLISHED', 'DEAD_LETTER')",
            name="ck_outbox_events_status",
        ),
    )
    op.create_index(
        "ix_outbox_events_status_occurred",
        "outbox_events",
        ["status", "occurred_at"],
    )
    op.create_index(
        "ix_outbox_events_business_occurred",
        "outbox_events",
        ["business_id", "occurred_at"],
    )


def downgrade() -> None:
    """Drop outbox_events table."""
    op.drop_index("ix_outbox_events_business_occurred", table_name="outbox_events")
    op.drop_index("ix_outbox_events_status_occurred", table_name="outbox_events")
    op.drop_table("outbox_events")
