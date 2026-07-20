"""Add canonical sales workflow foundations.

Revision ID: 20260720_0016a
Revises: 20260720_0015a
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260720_0016a"
down_revision: str | None = "20260720_0015a"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def audit_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    ]


def upgrade() -> None:
    op.add_column(
        "sales_invoice_lines",
        sa.Column("catalog_item_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_sales_invoice_lines_catalog_item",
        "sales_invoice_lines",
        "catalog_items",
        ["catalog_item_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_sales_invoice_lines_catalog_item_id",
        "sales_invoice_lines",
        ["catalog_item_id"],
    )
    op.add_column(
        "sales_invoices",
        sa.Column("round_off", sa.Numeric(18, 2), nullable=False, server_default="0"),
    )
    op.create_table(
        "sales_invoice_number_sequences",
        *audit_columns(),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("financial_year", sa.String(9), nullable=False),
        sa.Column("prefix", sa.String(20), nullable=False, server_default="INV"),
        sa.Column("next_value", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint(
            "business_id",
            "financial_year",
            name="uq_sales_invoice_sequence_business_year",
        ),
    )


def downgrade() -> None:
    op.drop_table("sales_invoice_number_sequences")
    op.drop_column("sales_invoices", "round_off")
    op.drop_index(
        "ix_sales_invoice_lines_catalog_item_id", table_name="sales_invoice_lines"
    )
    op.drop_constraint(
        "fk_sales_invoice_lines_catalog_item", "sales_invoice_lines", type_="foreignkey"
    )
    op.drop_column("sales_invoice_lines", "catalog_item_id")
