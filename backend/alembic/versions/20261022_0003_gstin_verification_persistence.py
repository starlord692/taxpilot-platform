"""Create persistent GSTIN verifications evidence table.

Revision ID: 20261022_0003
Revises: 20261022_0002
Create Date: 2026-10-22 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261022_0003"
down_revision: str | None = "20261022_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create gstin_verifications table with tenant isolation and indexes."""
    uuid_type = postgresql.UUID(as_uuid=True)

    evidence_status_enum = postgresql.ENUM(
        "FORMAT_VALIDATED_UNVERIFIED",
        "REGISTRATION_VERIFIED",
        "INVALIDATED",
        name="gstin_evidence_status",
        create_type=False,
    )
    evidence_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "gstin_verifications",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by", uuid_type, nullable=True),
        sa.Column("updated_by", uuid_type, nullable=True),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "business_id",
            uuid_type,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            uuid_type,
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("gstin", sa.String(length=15), nullable=False),
        sa.Column(
            "status",
            evidence_status_enum,
            nullable=False,
            server_default="FORMAT_VALIDATED_UNVERIFIED",
        ),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("trade_name", sa.String(length=255), nullable=True),
        sa.Column("registration_status", sa.String(length=50), nullable=True),
        sa.Column("evidence_source", sa.String(length=100), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload_hash", sa.String(length=64), nullable=True),
        sa.Column("evidence_metadata", sa.JSON(), nullable=True),
        sa.UniqueConstraint(
            "business_id",
            "gstin",
            name="uq_gstin_verifications_business_gstin",
        ),
    )

    op.create_index(
        "ix_gstin_verifications_business_id",
        "gstin_verifications",
        ["business_id"],
    )
    op.create_index(
        "ix_gstin_verifications_gstin",
        "gstin_verifications",
        ["gstin"],
    )
    op.create_index(
        "ix_gstin_verifications_status",
        "gstin_verifications",
        ["status"],
    )
    op.create_index(
        "ix_gstin_verifications_customer_id",
        "gstin_verifications",
        ["customer_id"],
    )


def downgrade() -> None:
    """Drop gstin_verifications table, indexes, and evidence status enum."""
    op.drop_index(
        "ix_gstin_verifications_customer_id",
        table_name="gstin_verifications",
    )
    op.drop_index(
        "ix_gstin_verifications_status",
        table_name="gstin_verifications",
    )
    op.drop_index(
        "ix_gstin_verifications_gstin",
        table_name="gstin_verifications",
    )
    op.drop_index(
        "ix_gstin_verifications_business_id",
        table_name="gstin_verifications",
    )
    op.drop_table("gstin_verifications")
    op.execute("DROP TYPE IF EXISTS gstin_evidence_status;")
