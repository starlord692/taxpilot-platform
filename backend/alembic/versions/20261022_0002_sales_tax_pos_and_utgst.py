"""Add place of supply to sales invoices and UTGST to lines.

Revision ID: 20261022_0002
Revises: 20261022_0001
Create Date: 2026-10-22 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261022_0002"
down_revision: str | None = "20261022_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add place_of_supply to sales_invoices and utgst_amount to lines."""
    op.add_column(
        "sales_invoices",
        sa.Column(
            "place_of_supply",
            sa.String(length=2),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_sales_invoices_place_of_supply",
        "sales_invoices",
        ["place_of_supply"],
    )
    op.add_column(
        "sales_invoice_lines",
        sa.Column(
            "utgst_amount",
            sa.Numeric(precision=18, scale=2),
            server_default="0.00",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove utgst_amount, place_of_supply index, and place_of_supply column."""
    op.drop_column("sales_invoice_lines", "utgst_amount")
    op.drop_index(
        "ix_sales_invoices_place_of_supply",
        table_name="sales_invoices",
    )
    op.drop_column("sales_invoices", "place_of_supply")
