"""Unit tests for DNA-005 deterministic Business DNA explanations."""

from dataclasses import replace

import pytest

from app.modules.business_dna import (
    BusinessDNAContext,
    BusinessDNAExplanationEngine,
    BusinessDNAProfileName,
    BusinessDNAProfileProvenance,
    FinancialProfile,
)
from tests.test_business_dna_models import context


def limited_context() -> BusinessDNAContext:
    """Create authoritative context with a material explicit financial limitation."""
    source = context()
    provenance = BusinessDNAProfileProvenance(
        source=source.financial.provenance.source,
        reference=source.financial.provenance.reference,
        description=source.financial.provenance.description,
        effective_at=source.financial.provenance.effective_at,
        limitations=("Financial profile has not been confirmed",),
    )
    return replace(source, financial=FinancialProfile(provenance=provenance))


def test_explanation_preserves_profiles_provenance_and_limitations() -> None:
    """Explanation retains only authoritative structured Business DNA information."""
    source = limited_context()

    explanation = BusinessDNAExplanationEngine().explain(context=source)

    assert explanation.context is source
    assert explanation.revision_history == ()
    assert tuple(item.profile for item in explanation.profile_coverage) == (
        BusinessDNAProfileName.IDENTITY,
        BusinessDNAProfileName.OPERATIONAL,
        BusinessDNAProfileName.FINANCIAL,
        BusinessDNAProfileName.COMPLIANCE,
        BusinessDNAProfileName.STRATEGIC,
    )
    assert explanation.profile_coverage[2].provenance is source.financial.provenance
    assert explanation.profile_coverage[2].limitations == (
        "Financial profile has not been confirmed",
    )
    assert explanation.limitations == ("Financial profile has not been confirmed",)


def test_explanation_preserves_supplied_revision_history_without_derivation() -> None:
    """Revision context is returned exactly as supplied after traceability checks."""
    initial = context()
    current = replace(initial, revision=2)
    history = (initial, current)

    explanation = BusinessDNAExplanationEngine().explain(
        context=current,
        revision_history=history,
    )

    assert explanation.revision_history is history
    assert tuple(item.revision for item in explanation.revision_history) == (1, 2)


def test_explanation_rejects_history_for_a_different_business() -> None:
    """Traceability must not combine separate businesses into one explanation."""
    current = context()
    unrelated = context()

    with pytest.raises(ValueError, match="explained business"):
        BusinessDNAExplanationEngine().explain(
            context=current,
            revision_history=(current, unrelated),
        )


def test_explanation_rejects_duplicate_revision_history() -> None:
    """Each revision may occur only once in structured explanatory context."""
    current = context()

    with pytest.raises(ValueError, match="duplicate revisions"):
        BusinessDNAExplanationEngine().explain(
            context=current,
            revision_history=(current, current),
        )


def test_explanation_requires_history_to_include_explained_context() -> None:
    """A supplied revision history must trace the context it claims to explain."""
    current = replace(context(), revision=2)
    earlier = replace(current, revision=1)

    with pytest.raises(ValueError, match="include the explained context"):
        BusinessDNAExplanationEngine().explain(
            context=current,
            revision_history=(earlier,),
        )


def test_explanation_is_deterministic_and_contains_no_generated_narrative() -> None:
    """Identical authoritative input produces an identical structured result."""
    engine = BusinessDNAExplanationEngine()
    source = context()

    first = engine.explain(context=source)
    second = engine.explain(context=source)

    assert first == second
    assert not hasattr(first, "narrative")
    assert not hasattr(first, "recommendations")
