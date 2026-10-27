"""Add warehouse fulfillment tracking to sales invoice lines.

Revision ID: 20261022_0001
Revises: 20261016_0001
Create Date: 2026-10-22 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261022_0001"
down_revision: str | None = "20261016_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable warehouse_id with foreign key and index to sales_invoice_lines."""
    op.add_column(
        "sales_invoice_lines",
        sa.Column(
            "warehouse_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_sales_invoice_lines_warehouse_id",
        "sales_invoice_lines",
        "inventory_warehouses",
        ["warehouse_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_sales_invoice_lines_warehouse_id",
        "sales_invoice_lines",
        ["warehouse_id"],
    )


def downgrade() -> None:
    """Remove warehouse_id column, foreign key, and index from sales_invoice_lines."""
    op.drop_index(
        "ix_sales_invoice_lines_warehouse_id",
        table_name="sales_invoice_lines",
    )
    op.drop_constraint(
        "fk_sales_invoice_lines_warehouse_id",
        "sales_invoice_lines",
        type_="foreignkey",
    )
    op.drop_column("sales_invoice_lines", "warehouse_id")
