"""Unit tests for CONF-005 deterministic Business Confidence explanations."""

from dataclasses import FrozenInstanceError

import pytest

from app.modules.business_confidence import (
    BusinessConfidenceAssessment,
    BusinessConfidenceExplanationEngine,
    BusinessUnderstandingCoverage,
)
from tests.test_business_confidence_models import assessment


def limited_assessment() -> BusinessConfidenceAssessment:
    """Create one authoritative assessment with coverage and global limitations."""
    source = assessment()
    return source


def test_explanation_preserves_only_authoritative_assessment_structures() -> None:
    """Explanation retains coverage, evidence, context, provenance, time, and gaps."""
    source = limited_assessment()

    explanation = BusinessConfidenceExplanationEngine().explain(assessment=source)

    assert explanation.assessment is source
    assert explanation.business_id == source.business_id
    assert explanation.assessed_at == source.assessed_at
    assert explanation.coverage is source.coverage
    assert explanation.coverage[0].evidence is source.coverage[0].evidence
    assert explanation.approved_context is source.approved_context
    assert explanation.approved_context[0].reference == "business-dna-revision-1"
    assert explanation.limitations is source.limitations


def test_explanation_preserves_coverage_level_limitations_exactly() -> None:
    """The engine neither hides nor deduplicates supplied explicit limitations."""
    source = assessment()
    coverage = BusinessUnderstandingCoverage(
        area="customer context",
        limitations=("Customer records are not yet available",),
    )
    source = type(source)(
        business_id=source.business_id,
        assessed_at=source.assessed_at,
        coverage=(source.coverage[0], coverage),
        approved_context=source.approved_context,
        limitations=("Customer context is not yet available",) * 2,
    )

    explanation = BusinessConfidenceExplanationEngine().explain(assessment=source)

    assert explanation.coverage[1] is coverage
    assert explanation.coverage[1].limitations == (
        "Customer records are not yet available",
    )
    assert explanation.limitations == (
        "Customer context is not yet available",
        "Customer context is not yet available",
    )


def test_explanation_is_immutable() -> None:
    """The structured explanation cannot be modified after it is produced."""
    explanation = BusinessConfidenceExplanationEngine().explain(
        assessment=limited_assessment()
    )

    with pytest.raises(FrozenInstanceError):
        explanation.assessed_at = explanation.assessed_at  # type: ignore[misc]


def test_explanation_is_deterministic_and_contains_no_generated_content() -> None:
    """Identical authoritative input produces identical structural output only."""
    engine = BusinessConfidenceExplanationEngine()
    source = limited_assessment()

    assert engine.explain(assessment=source) == engine.explain(assessment=source)
    explanation = engine.explain(assessment=source)
    assert not hasattr(explanation, "narrative")
    assert not hasattr(explanation, "recommendations")
    assert not hasattr(explanation, "score")
    assert not hasattr(explanation, "policy_outcome")
