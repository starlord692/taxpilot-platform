"""Add canonical invoice financial configuration snapshots.

Revision ID: 20260720_0016c
Revises: 20260720_0016a
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260720_0016c"
down_revision: str | None = "20260720_0016a"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sales_invoices", sa.Column("currency", sa.String(3), nullable=True))
    op.add_column(
        "sales_invoices", sa.Column("payment_terms_days", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("sales_invoices", "payment_terms_days")
    op.drop_column("sales_invoices", "currency")
