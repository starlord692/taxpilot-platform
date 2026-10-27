"""Alter outbox_events business foreign key to ON DELETE RESTRICT."""

from collections.abc import Sequence

from alembic import op

revision: str = "20261015_0001"
down_revision: str | None = "20261013_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Alter outbox_events.business_id foreign key constraint to ON DELETE RESTRICT."""
    op.drop_constraint(
        "outbox_events_business_id_fkey",
        "outbox_events",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "outbox_events_business_id_fkey",
        "outbox_events",
        "businesses",
        ["business_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Revert outbox_events.business_id foreign key constraint to ON DELETE CASCADE."""
    op.drop_constraint(
        "outbox_events_business_id_fkey",
        "outbox_events",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "outbox_events_business_id_fkey",
        "outbox_events",
        "businesses",
        ["business_id"],
        ["id"],
        ondelete="CASCADE",
    )
