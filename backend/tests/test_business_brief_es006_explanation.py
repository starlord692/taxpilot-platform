"""Unit tests for BRIEF-005 deterministic ES-006 Business Brief explanations."""

from dataclasses import FrozenInstanceError
from datetime import timedelta

import pytest

from app.modules.business_brief.es006 import (
    ApprovedBriefContext,
    BusinessBriefExplanationEngine,
    BusinessBriefSourceReference,
    DeterministicBriefEvidence,
)
from tests.test_business_brief_es006_models import BRIEF_AT, brief, narrative_item


def test_explanation_preserves_authoritative_brief_structures_exactly() -> None:
    """Explanation retains supplied content, ownership, timing, and limitations."""
    source = brief()

    explanation = BusinessBriefExplanationEngine().explain(brief=source)

    assert explanation.brief is source
    assert explanation.business_id == source.business_id
    assert explanation.brief_at == source.brief_at
    assert explanation.narrative_items is source.narrative_items
    assert explanation.recommendations is source.recommendations
    assert explanation.limitations is source.limitations
    assert explanation.narrative_items[0].source_references is (
        source.narrative_items[0].source_references
    )
    assert explanation.narrative_items[0].evidence is source.narrative_items[0].evidence
    assert explanation.narrative_items[0].approved_context is (
        source.narrative_items[0].approved_context
    )


def test_explanation_preserves_recommendation_traceability_exactly() -> None:
    """Supplied recommendation reasoning and traceability remain unchanged."""
    source = brief()

    explanation = BusinessBriefExplanationEngine().explain(brief=source)

    assert explanation.recommendations[0] is source.recommendations[0]
    assert (
        explanation.recommendations[0].statement == source.recommendations[0].statement
    )
    assert (
        explanation.recommendations[0].reasoning == source.recommendations[0].reasoning
    )
    assert explanation.recommendations[0].source_references is (
        source.recommendations[0].source_references
    )
    assert explanation.recommendations[0].evidence is (
        source.recommendations[0].evidence
    )
    assert explanation.recommendations[0].approved_context is (
        source.recommendations[0].approved_context
    )
    assert explanation.recommendations[0].limitations is (
        source.recommendations[0].limitations
    )


def test_explanation_is_immutable_and_deterministic() -> None:
    """Identical authoritative input produces one immutable structural result."""
    source = brief()
    engine = BusinessBriefExplanationEngine()

    first = engine.explain(brief=source)

    assert first == engine.explain(brief=source)
    with pytest.raises(FrozenInstanceError):
        first.brief_at = source.brief_at  # type: ignore[misc]


def test_explanation_contains_no_generated_content_or_policy_result() -> None:
    """The result has only authoritative structures and no generated behavior."""
    explanation = BusinessBriefExplanationEngine().explain(brief=brief())

    assert not hasattr(explanation, "generated_narrative")
    assert not hasattr(explanation, "generated_recommendations")
    assert not hasattr(explanation, "policy_outcome")
    assert not hasattr(explanation, "ranking")
    assert not hasattr(explanation, "priorities")


def test_explanation_rejects_untraceable_narrative_structure() -> None:
    """A bypassed narrative invariant cannot be accepted as an explanation basis."""
    item = narrative_item()
    object.__setattr__(item, "source_references", ())
    source = brief()
    object.__setattr__(source, "narrative_items", (item,))

    with pytest.raises(ValueError, match="requires source references"):
        BusinessBriefExplanationEngine().explain(brief=source)


def test_explanation_rejects_duplicate_evidence_in_bypassed_structure() -> None:
    """Traceability cannot contain duplicate deterministic evidence references."""
    item = narrative_item()
    object.__setattr__(item, "evidence", (item.evidence[0], item.evidence[0]))
    source = brief()
    object.__setattr__(source, "narrative_items", (item,))

    with pytest.raises(ValueError, match="evidence must not be duplicated"):
        BusinessBriefExplanationEngine().explain(brief=source)


def test_explanation_rejects_future_traceability_in_bypassed_structure() -> None:
    """Explanation preserves the authoritative Brief point-in-time boundary."""
    item = narrative_item()
    future_source = BusinessBriefSourceReference(
        kind=item.source_references[0].kind,
        source_owner=item.source_references[0].source_owner,
        reference="future-source",
        description="Source after the Brief time",
        effective_at=BRIEF_AT + timedelta(seconds=1),
    )
    object.__setattr__(item, "source_references", (future_source,))
    source = brief()
    object.__setattr__(source, "narrative_items", (item,))

    with pytest.raises(ValueError, match="cannot be effective after brief"):
        BusinessBriefExplanationEngine().explain(brief=source)


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        (
            "evidence",
            DeterministicBriefEvidence(
                source_owner="accounting",
                reference="future-evidence",
                description="Evidence after the Brief time",
                observed_at=BRIEF_AT + timedelta(seconds=1),
            ),
            "evidence cannot be observed after brief",
        ),
        (
            "approved_context",
            ApprovedBriefContext(
                source_owner="business_dna",
                reference="future-context",
                description="Context after the Brief time",
                effective_at=BRIEF_AT + timedelta(seconds=1),
            ),
            "context cannot be effective after brief",
        ),
    ],
)
def test_explanation_rejects_future_evidence_or_context(
    field: str,
    replacement: DeterministicBriefEvidence | ApprovedBriefContext,
    message: str,
) -> None:
    """Every retained evidence and context structure must predate the Brief."""
    item = narrative_item()
    object.__setattr__(item, field, (replacement,))
    source = brief()
    object.__setattr__(source, "narrative_items", (item,))

    with pytest.raises(ValueError, match=message):
        BusinessBriefExplanationEngine().explain(brief=source)
