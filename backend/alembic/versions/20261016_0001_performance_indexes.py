"""Add composite and partial indexes for persistence performance.

Revision ID: 20261016_0001
Revises: 20261015_0001
Create Date: 2026-10-16 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261016_0001"
down_revision: str | None = "20261015_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create approved composite and partial performance indexes.

    Includes IX-1, IX-2, IX-3, IX-5, and IX-6.
    Note: IX-4 (ix_gl_entries_account_date) is omitted per empirical evidence
    showing no material benefit under tenant-isolated queries and lack of
    application endpoints.
    IX-7 (ix_outbox_events_status_unprocessed) remains deferred per FD-1
    dormant relay policy.
    """
    # IX-1: Sales invoices business chronological listing
    op.create_index(
        "ix_sales_invoices_business_date",
        "sales_invoices",
        ["business_id", sa.text("invoice_date DESC"), sa.text("created_at DESC")],
        postgresql_where=sa.text("is_deleted = false"),
    )

    # IX-2: Purchase invoices business chronological listing
    op.create_index(
        "ix_purchase_invoices_business_date",
        "purchase_invoices",
        ["business_id", sa.text("invoice_date DESC"), sa.text("created_at DESC")],
        postgresql_where=sa.text("is_deleted = false"),
    )

    # IX-3: General ledger business chronological range scan
    op.create_index(
        "ix_gl_entries_business_date",
        "general_ledger_entries",
        ["business_id", sa.text("transaction_date ASC"), sa.text("created_at ASC")],
        postgresql_where=sa.text("is_deleted = false"),
    )

    # IX-5: Inventory stock movement trace by reference
    op.create_index(
        "ix_stock_movements_reference",
        "inventory_stock_movements",
        ["business_id", "reference_type", "reference_id"],
    )

    # IX-6: Documents business uploaded reverse-chronological feed
    op.create_index(
        "ix_documents_business_uploaded",
        "documents",
        ["business_id", sa.text("uploaded_at DESC")],
        postgresql_where=sa.text("is_deleted = false"),
    )


def downgrade() -> None:
    """Drop performance indexes in reverse order."""
    op.drop_index(
        "ix_documents_business_uploaded",
        table_name="documents",
    )
    op.drop_index(
        "ix_stock_movements_reference",
        table_name="inventory_stock_movements",
    )
    op.drop_index(
        "ix_gl_entries_business_date",
        table_name="general_ledger_entries",
    )
    op.drop_index(
        "ix_purchase_invoices_business_date",
        table_name="purchase_invoices",
    )
    op.drop_index(
        "ix_sales_invoices_business_date",
        table_name="sales_invoices",
    )
