"""Create Accounting AFPE context and evidence persistence tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260913_0001"
down_revision: str | None = "20260726_0001_rc1_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create durable AFPE context, artifact, and lineage records."""
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
        "accounting_observation_periods",
        *common_columns(),
        sa.Column("business_id", uuid_type, nullable=False),
        sa.Column("observation_period_id", sa.String(255), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("granularity", sa.String(64), nullable=False),
        sa.Column("period_type", sa.String(16), nullable=False),
        sa.Column("inclusion_basis", sa.String(32), nullable=False),
        sa.Column("period_policy_id", sa.String(255), nullable=False),
        sa.Column("period_policy_version", sa.String(64), nullable=False),
        sa.Column("period_state", sa.String(16), nullable=False),
        sa.Column("reconstruction_context_id", sa.String(255), nullable=True),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["business_id"], ["businesses.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "business_id",
            "observation_period_id",
            name="uq_afpe_observation_period_business_identity",
        ),
        sa.Index("ix_afpe_observation_period_business", "business_id"),
        sa.CheckConstraint("period_start < period_end", name="ck_afpe_period_bounds"),
        sa.CheckConstraint(
            "period_type IN ('CALENDAR', 'FISCAL')", name="ck_afpe_period_type"
        ),
        sa.CheckConstraint(
            "inclusion_basis = 'POSTING_DATE'",
            name="ck_afpe_period_inclusion_basis",
        ),
        sa.CheckConstraint(
            "period_state IN ('OPEN', 'CLOSED')", name="ck_afpe_period_state"
        ),
    )
    op.create_table(
        "accounting_comparison_contexts",
        *common_columns(),
        sa.Column("business_id", uuid_type, nullable=False),
        sa.Column("current_observation_period_id", sa.String(255), nullable=False),
        sa.Column("comparison_observation_period_id", sa.String(255), nullable=False),
        sa.Column("comparison_kind", sa.String(64), nullable=False),
        sa.Column("availability_state", sa.String(32), nullable=False),
        sa.Column("limitations", postgresql.JSONB(), nullable=False),
        sa.Column("provenance", postgresql.JSONB(), nullable=False),
        sa.Column("policy_context", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_id"], ["businesses.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "business_id",
            "current_observation_period_id",
            "comparison_observation_period_id",
            "comparison_kind",
            name="uq_afpe_comparison_context",
        ),
        sa.Index("ix_afpe_comparison_context_business", "business_id"),
    )
    op.create_table(
        "accounting_reconstruction_contexts",
        *common_columns(),
        sa.Column("business_id", uuid_type, nullable=False),
        sa.Column("reconstruction_context_id", sa.String(255), nullable=False),
        sa.Column("observation_period_id", sa.String(255), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("context_payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_id"], ["businesses.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "business_id",
            "reconstruction_context_id",
            name="uq_afpe_reconstruction_context",
        ),
        sa.Index("ix_afpe_reconstruction_business", "business_id"),
    )
    op.create_table(
        "accounting_historical_evidence",
        *common_columns(),
        sa.Column("business_id", uuid_type, nullable=False),
        sa.Column("observation_period_id", sa.String(255), nullable=False),
        sa.Column("evidence_result_id", sa.String(255), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("publication_event_id", sa.String(255), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_id"], ["businesses.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "business_id",
            "evidence_result_id",
            name="uq_afpe_historical_evidence_identity",
        ),
        sa.Index(
            "ix_afpe_historical_evidence_business_period",
            "business_id",
            "observation_period_id",
        ),
    )
    op.create_table(
        "accounting_evidence_lineage",
        *common_columns(),
        sa.Column("business_id", uuid_type, nullable=False),
        sa.Column("evidence_result_id", sa.String(255), nullable=False),
        sa.Column("predecessor_evidence_result_id", sa.String(255), nullable=True),
        sa.Column("relationship_type", sa.String(64), nullable=False),
        sa.Column("relationship_payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_id"], ["businesses.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "business_id",
            "evidence_result_id",
            "predecessor_evidence_result_id",
            "relationship_type",
            name="uq_afpe_evidence_lineage",
        ),
        sa.Index("ix_afpe_lineage_business", "business_id"),
    )


def downgrade() -> None:
    """Drop only AFPE-owned tables."""
    op.drop_table("accounting_evidence_lineage")
    op.drop_table("accounting_historical_evidence")
    op.drop_table("accounting_reconstruction_contexts")
    op.drop_table("accounting_comparison_contexts")
    op.drop_table("accounting_observation_periods")
