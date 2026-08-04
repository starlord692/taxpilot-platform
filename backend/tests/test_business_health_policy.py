"""Unit tests for BH-004 deterministic Business Health policy rules."""

import pytest

from app.modules.business_health.models import (
    DeterministicEvidenceReference,
    HealthContributor,
    HealthDimension,
    HealthDimensionEvidence,
    HealthState,
)
from app.modules.business_health.policy import (
    MOST_CONCERNING_DIMENSION_RULE,
    BusinessHealthPolicyEngine,
)
from app.modules.business_health.service import HealthDimensionInput


def evidence(dimension: HealthDimension) -> DeterministicEvidenceReference:
    """Create deterministic evidence for an authoritative test input."""
    return DeterministicEvidenceReference(
        source=f"{dimension.value}-domain",
        reference=f"{dimension.value}-record",
        description=f"Verified {dimension.value} information",
    )


def dimensions(
    *,
    financial_state: HealthState = HealthState.HEALTHY,
    compliance_state: HealthState = HealthState.HEALTHY,
    contributors: bool = False,
) -> tuple[HealthDimensionInput, ...]:
    """Create all canonical dimension inputs without repository access."""
    states = {
        HealthDimension.FINANCIAL: financial_state,
        HealthDimension.COMPLIANCE: compliance_state,
        HealthDimension.OPERATIONAL: HealthState.HEALTHY,
        HealthDimension.CUSTOMER: HealthState.HEALTHY,
        HealthDimension.SUPPLIER: HealthState.HEALTHY,
        HealthDimension.GROWTH: HealthState.HEALTHY,
    }
    return tuple(
        HealthDimensionInput(
            dimension=dimension,
            state=state,
            evidence=HealthDimensionEvidence(
                dimension=dimension,
                evidence=(evidence(dimension),),
            ),
            contributors=(
                HealthContributor(
                    dimension=dimension,
                    statement=f"{dimension.value.title()} contributor.",
                    evidence=(evidence(dimension),),
                ),
            )
            if contributors
            else (),
        )
        for dimension, state in states.items()
    )


def test_policy_selects_the_most_concerning_canonical_state() -> None:
    """The approved initial rule yields the most concerning dimension state."""
    outcome = BusinessHealthPolicyEngine().evaluate(
        dimensions(financial_state=HealthState.WATCH)
    )

    assert outcome.state is HealthState.WATCH
    assert outcome.applied_rule == MOST_CONCERNING_DIMENSION_RULE
    assert outcome.decisive_dimensions == (HealthDimension.FINANCIAL,)


def test_policy_includes_all_dimensions_tied_at_the_decisive_state() -> None:
    """Explainability preserves every dimension that drives the outcome."""
    outcome = BusinessHealthPolicyEngine().evaluate(
        dimensions(
            financial_state=HealthState.AT_RISK,
            compliance_state=HealthState.AT_RISK,
            contributors=True,
        )
    )

    assert outcome.state is HealthState.AT_RISK
    assert outcome.decisive_dimensions == (
        HealthDimension.FINANCIAL,
        HealthDimension.COMPLIANCE,
    )
    assert {item.dimension for item in outcome.contributors} == {
        HealthDimension.FINANCIAL,
        HealthDimension.COMPLIANCE,
    }


def test_policy_rejects_a_non_whole_business_input() -> None:
    """A departmental subset cannot become a Business Health outcome."""
    with pytest.raises(ValueError, match="all canonical health dimensions"):
        BusinessHealthPolicyEngine().evaluate(dimensions()[:-1])


def test_policy_rejects_duplicate_dimensions() -> None:
    """Each canonical dimension has one authoritative policy input."""
    source = dimensions()
    duplicate = source[:-1] + (source[0],)

    with pytest.raises(ValueError, match="must not be duplicated"):
        BusinessHealthPolicyEngine().evaluate(duplicate)
