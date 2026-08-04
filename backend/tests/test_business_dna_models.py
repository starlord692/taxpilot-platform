"""Unit tests for DNA-001 immutable descriptive Business DNA domain models."""

import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from app.modules.business_dna import (
    BusinessDNAContext,
    BusinessDNAContextSource,
    BusinessDNAProfileProvenance,
    BusinessIdentityProfile,
    ComplianceProfile,
    FinancialProfile,
    OperationalProfile,
    StrategicProfile,
)

RECORDED_AT = datetime(2026, 8, 5, 13, 0, tzinfo=UTC)


def provenance(*, limitations: tuple[str, ...] = ()) -> BusinessDNAProfileProvenance:
    """Create approved, non-inferred profile provenance for a test fixture."""
    return BusinessDNAProfileProvenance(
        source=BusinessDNAContextSource.OWNER_CONFIRMED,
        reference="owner-confirmation-1",
        description="Owner-confirmed business understanding",
        effective_at=RECORDED_AT,
        limitations=limitations,
    )


def context() -> BusinessDNAContext:
    """Create a complete descriptive Business DNA context."""
    return BusinessDNAContext(
        business_id=uuid.uuid4(),
        revision=1,
        recorded_at=RECORDED_AT,
        identity=BusinessIdentityProfile(
            provenance=provenance(),
            industry="Retail",
            business_model="Direct sales",
            size="Small business",
            legal_structure="Proprietorship",
            geographic_operation="Karnataka",
            tax_registrations=("GST",),
        ),
        operational=OperationalProfile(
            provenance=provenance(),
            products_or_services=("Consumer goods",),
            sales_channels=("Storefront",),
            procurement_model="Supplier purchasing",
            inventory_behaviour="Stocked inventory",
            revenue_cycle="Point of sale",
            expense_patterns="Operating expenses",
        ),
        financial=FinancialProfile(
            provenance=provenance(),
            revenue_model="Product sales",
            margin_expectations="Category-dependent margins",
            cash_flow_characteristics="Regular operating cash flow",
            seasonal_income="Festival demand",
            payment_cycles="Supplier credit cycle",
        ),
        compliance=ComplianceProfile(
            provenance=provenance(),
            gst_context="GST registered",
            income_tax_context="Income tax applicable",
            filing_frequency="Periodic filing",
            industry_compliance=("Retail records",),
        ),
        strategic=StrategicProfile(
            provenance=provenance(),
            owner_priorities=("Growth", "Cash preservation"),
        ),
    )


def test_context_preserves_all_five_canonical_descriptive_profiles() -> None:
    """Business DNA contains all approved profiles without an evaluation result."""
    result = context()

    assert result.identity.industry == "Retail"
    assert result.operational.sales_channels == ("Storefront",)
    assert result.financial.revenue_model == "Product sales"
    assert result.compliance.gst_context == "GST registered"
    assert result.strategic.owner_priorities == ("Growth", "Cash preservation")


def test_profile_can_preserve_explicit_incomplete_context_without_inference() -> None:
    """Absent descriptive values require an explicit limitation instead of inference."""
    profile = FinancialProfile(
        provenance=provenance(limitations=("Financial profile not yet confirmed",)),
    )

    assert profile.provenance.limitations == ("Financial profile not yet confirmed",)


def test_profile_accepts_declared_list_based_context_without_inference() -> None:
    """Declared list-based facts are descriptive context in their own right."""
    profile = OperationalProfile(
        provenance=provenance(),
        sales_channels=("Storefront",),
    )

    assert profile.sales_channels == ("Storefront",)


def test_profile_rejects_missing_context_without_an_explicit_limitation() -> None:
    """The model cannot silently replace missing Business DNA with a guess."""
    with pytest.raises(ValueError, match="explicit limitation"):
        FinancialProfile(provenance=provenance())


def test_provenance_accepts_only_authoritative_source_categories() -> None:
    """Business DNA sources are explicit and do not include AI inference."""
    result = provenance()

    assert result.source is BusinessDNAContextSource.OWNER_CONFIRMED
    assert "ai" not in {source.value for source in BusinessDNAContextSource}


def test_context_requires_a_positive_revision_for_explicit_evolution() -> None:
    """Business DNA evolution is explicit rather than an implicit mutation."""
    source = context()

    with pytest.raises(ValueError, match="revision must be positive"):
        BusinessDNAContext(
            business_id=source.business_id,
            revision=0,
            recorded_at=source.recorded_at,
            identity=source.identity,
            operational=source.operational,
            financial=source.financial,
            compliance=source.compliance,
            strategic=source.strategic,
        )


def test_business_dna_models_are_immutable() -> None:
    """Authoritative descriptive context cannot be mutated after creation."""
    result = context()

    with pytest.raises(FrozenInstanceError):
        result.revision = 2  # type: ignore[misc]
