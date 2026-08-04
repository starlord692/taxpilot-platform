"""Unit tests for BH-005 deterministic Business Health explanations."""

import uuid
from datetime import UTC, datetime

import pytest

from app.modules.business_health.explanation import BusinessHealthExplanationEngine
from app.modules.business_health.models import (
    BusinessHealthAssessment,
    DeterministicEvidenceReference,
    HealthContributor,
    HealthDimension,
    HealthDimensionEvidence,
    HealthState,
)
from app.modules.business_health.policy import BusinessHealthPolicyOutcome

ASSESSED_AT = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


def evidence(dimension: HealthDimension) -> DeterministicEvidenceReference:
    """Create deterministic evidence for an authoritative assessment fixture."""
    return DeterministicEvidenceReference(
        source=f"{dimension.value}-domain",
        reference=f"{dimension.value}-record",
        description=f"Verified {dimension.value} information",
    )


def dimension_evidence() -> tuple[HealthDimensionEvidence, ...]:
    """Create all canonical dimension evidence with one explicit limitation."""
    return tuple(
        HealthDimensionEvidence(
            dimension=dimension,
            evidence=(evidence(dimension),),
            limitations=("Supplier history is incomplete",)
            if dimension is HealthDimension.SUPPLIER
            else (),
        )
        for dimension in HealthDimension
    )


def contributor() -> HealthContributor:
    """Create an evidence-backed material contributor."""
    return HealthContributor(
        dimension=HealthDimension.FINANCIAL,
        statement="Overdue receivables increased.",
        evidence=(evidence(HealthDimension.FINANCIAL),),
    )


def assessment() -> BusinessHealthAssessment:
    """Create a complete authoritative assessment fixture."""
    return BusinessHealthAssessment(
        business_id=uuid.uuid4(),
        assessed_at=ASSESSED_AT,
        state=HealthState.WATCH,
        dimension_evidence=dimension_evidence(),
        contributors=(contributor(),),
        limitations=("Recent reconciliation is pending",),
    )


def policy_outcome(
    *,
    state: HealthState = HealthState.WATCH,
    dimensions: tuple[HealthDimension, ...] = (HealthDimension.FINANCIAL,),
    contributors: tuple[HealthContributor, ...] | None = None,
) -> BusinessHealthPolicyOutcome:
    """Create an authoritative policy outcome fixture."""
    return BusinessHealthPolicyOutcome(
        state=state,
        applied_rule="most_concerning_canonical_dimension",
        decisive_dimensions=dimensions,
        contributors=(contributor(),) if contributors is None else contributors,
    )


def test_explanation_preserves_authoritative_policy_and_evidence() -> None:
    """Explanation exposes policy, evidence, contributors, and limitations intact."""
    source_assessment = assessment()
    source_policy = policy_outcome(contributors=source_assessment.contributors)

    explanation = BusinessHealthExplanationEngine().explain(
        assessment=source_assessment,
        policy_outcome=source_policy,
    )

    assert explanation.state is HealthState.WATCH
    assert explanation.applied_rule == "most_concerning_canonical_dimension"
    assert explanation.decisive_dimensions == (HealthDimension.FINANCIAL,)
    assert explanation.material_contributors == source_assessment.contributors
    assert explanation.dimension_evidence == source_assessment.dimension_evidence
    assert explanation.limitations == (
        "Recent reconciliation is pending",
        "Supplier history is incomplete",
    )


def test_explanation_rejects_policy_outcome_with_a_different_state() -> None:
    """Explanation cannot change the authoritative Health state."""
    with pytest.raises(ValueError, match="must match assessment state"):
        BusinessHealthExplanationEngine().explain(
            assessment=assessment(),
            policy_outcome=policy_outcome(state=HealthState.HEALTHY),
        )


def test_explanation_rejects_duplicate_decisive_dimension() -> None:
    """Explanation preserves a unique set of decisive dimensions."""
    source_assessment = assessment()
    with pytest.raises(ValueError, match="must not be duplicated"):
        BusinessHealthExplanationEngine().explain(
            assessment=source_assessment,
            policy_outcome=policy_outcome(
                dimensions=(HealthDimension.FINANCIAL, HealthDimension.FINANCIAL),
                contributors=source_assessment.contributors,
            ),
        )


def test_explanation_rejects_untraceable_material_contributor() -> None:
    """Explanation cannot introduce a contributor absent from assessment output."""
    unknown = HealthContributor(
        dimension=HealthDimension.FINANCIAL,
        statement="Unknown contributor.",
        evidence=(evidence(HealthDimension.FINANCIAL),),
    )
    with pytest.raises(ValueError, match="contributors must exist"):
        BusinessHealthExplanationEngine().explain(
            assessment=assessment(),
            policy_outcome=policy_outcome(contributors=(unknown,)),
        )
