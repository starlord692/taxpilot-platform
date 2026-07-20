"""Add canonical catalog and inventory capability profile.

Revision ID: 20260720_0015a
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260720_0015a"
down_revision: str | None = None
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
    op.create_table(
        "catalog_items",
        *audit_columns(),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(80), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("item_type", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("category", sa.String(120), nullable=True),
        sa.Column(
            "purchase_price", sa.Numeric(18, 2), nullable=False, server_default="0"
        ),
        sa.Column(
            "selling_price", sa.Numeric(18, 2), nullable=False, server_default="0"
        ),
        sa.Column("default_unit", sa.String(30), nullable=False),
        sa.Column("barcode", sa.String(100), nullable=True),
        sa.Column("hsn_code", sa.String(8), nullable=True),
        sa.Column("sac_code", sa.String(8), nullable=True),
        sa.Column("gst_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("cess_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "item_type IN ('product', 'service')", name="ck_catalog_item_type"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived')", name="ck_catalog_item_status"
        ),
        sa.CheckConstraint(
            "NOT (hsn_code IS NOT NULL AND sac_code IS NOT NULL)",
            name="ck_catalog_single_tax_code",
        ),
        sa.UniqueConstraint(
            "business_id", "code", name="uq_catalog_items_business_code"
        ),
    )
    op.create_index(
        "ix_catalog_items_business_type", "catalog_items", ["business_id", "item_type"]
    )
    op.create_index("ix_catalog_items_name", "catalog_items", ["name"])
    op.create_table(
        "inventory_item_profiles",
        *audit_columns(),
        sa.Column(
            "catalog_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("catalog_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "legacy_product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inventory_products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "stock_tracking", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("reorder_level", sa.Numeric(18, 4), nullable=True),
        sa.Column("opening_quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("opening_value", sa.Numeric(18, 2), nullable=True),
        sa.Column(
            "default_warehouse_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inventory_warehouses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "catalog_item_id", name="uq_inventory_profiles_catalog_item"
        ),
        sa.UniqueConstraint(
            "legacy_product_id", name="uq_inventory_profiles_legacy_product"
        ),
    )
    op.execute(
        """INSERT INTO catalog_items (id,business_id,code,name,description,item_type,status,category,purchase_price,selling_price,default_unit,barcode,gst_rate,cess_rate,created_at,updated_at,created_by,updated_by,is_deleted,deleted_at,version) SELECT id,business_id,sku,name,description,'product',CASE WHEN is_active THEN 'active' ELSE 'archived' END,category,purchase_price,selling_price,unit_of_measure,barcode,0,0,created_at,updated_at,created_by,updated_by,is_deleted,deleted_at,version FROM inventory_products"""  # noqa: E501
    )
    op.execute(
        """INSERT INTO inventory_item_profiles (id,catalog_item_id,legacy_product_id,stock_tracking,reorder_level,created_at,updated_at,created_by,updated_by,is_deleted,deleted_at,version) SELECT id,id,id,TRUE,reorder_level,created_at,updated_at,created_by,updated_by,FALSE,NULL,1 FROM inventory_products"""  # noqa: E501
    )


def downgrade() -> None:
    op.drop_table("inventory_item_profiles")
    op.drop_index("ix_catalog_items_name", table_name="catalog_items")
    op.drop_index("ix_catalog_items_business_type", table_name="catalog_items")
    op.drop_table("catalog_items")
