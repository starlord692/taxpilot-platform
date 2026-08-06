"""ES-007 Phase 3 cutover-validation tests for the temporary compatibility facade."""

import uuid
from dataclasses import replace

import pytest

from app.modules.business_brief.es006 import (
    BusinessBriefInput,
    BusinessBriefNarrativeItem,
    BusinessBriefSourceKind,
    BusinessBriefSourceReference,
)
from app.modules.business_brief.exceptions import BusinessBriefSourceMismatchError
from app.modules.business_brief.models import BusinessBriefRequest
from tests.test_business_brief_compatibility_facade import (
    canonical_input,
    descriptor,
    facade,
    item,
)
from tests.test_business_brief_service import (
    AS_OF,
    FakeAuditRepository,
    make_service,
)

pytestmark = pytest.mark.asyncio


def equivalent_canonical_input(business_id: uuid.UUID) -> BusinessBriefInput:
    """Supply canonical structures corresponding to characterized ES-001 aliases."""
    return BusinessBriefInput(
        business_id=business_id,
        brief_at=AS_OF,
        narrative_items=(
            BusinessBriefNarrativeItem(
                statement="Business activity requires attention.",
                source_references=(
                    BusinessBriefSourceReference(
                        kind=BusinessBriefSourceKind.BUSINESS_DNA,
                        source_owner="business_dna",
                        reference="dna-1",
                        description="Retail business",
                        effective_at=AS_OF,
                    ),
                ),
            ),
            BusinessBriefNarrativeItem(
                statement="Current condition is healthy.",
                source_references=(
                    BusinessBriefSourceReference(
                        kind=BusinessBriefSourceKind.BUSINESS_HEALTH,
                        source_owner="business_health",
                        reference="health-1",
                        description="Current condition",
                        effective_at=AS_OF,
                    ),
                ),
            ),
            BusinessBriefNarrativeItem(
                statement="Observed movement is improving.",
                source_references=(
                    BusinessBriefSourceReference(
                        kind=BusinessBriefSourceKind.BUSINESS_MOMENTUM,
                        source_owner="business_momentum",
                        reference="momentum-1",
                        description="Observed movement",
                        effective_at=AS_OF,
                    ),
                ),
            ),
            BusinessBriefNarrativeItem(
                statement="Understanding is reliable with stated limits.",
                source_references=(
                    BusinessBriefSourceReference(
                        kind=BusinessBriefSourceKind.BUSINESS_CONFIDENCE,
                        source_owner="business_confidence",
                        reference="confidence-1",
                        description="Reliability context",
                        effective_at=AS_OF,
                    ),
                ),
            ),
        ),
        limitations=("Customer context is not yet available",),
    )


async def test_available_aliases_match_characterized_es001_response() -> None:
    """Available Health, Momentum, Confidence, and context aliases remain equivalent."""
    business_id = uuid.uuid4()
    user_id = uuid.uuid4()
    request = BusinessBriefRequest(
        business_id=business_id,
        user_id=user_id,
        as_of=AS_OF,
    )
    legacy = await make_service(business_id=business_id).get_brief(request)
    supplied = equivalent_canonical_input(business_id)
    migration, _, _, _ = facade(value=supplied, projection=descriptor(supplied))

    projected = await migration.get_brief(request)

    assert projected.context is not None
    assert projected.narrative is not None
    assert legacy.context is not None
    assert legacy.narrative is not None
    assert projected.business_id == legacy.business_id
    assert projected.requested_by == legacy.requested_by
    assert projected.as_of == legacy.as_of
    assert projected.context.current_understanding.text == (
        legacy.context.current_understanding.text
    )
    assert projected.narrative.health.kind is legacy.narrative.health.kind
    assert (
        projected.narrative.health.statement.text
        == legacy.narrative.health.statement.text
    )
    assert projected.narrative.momentum.kind is legacy.narrative.momentum.kind
    assert projected.narrative.momentum.statement.text == (
        legacy.narrative.momentum.statement.text
    )
    assert projected.narrative.confidence.kind is legacy.narrative.confidence.kind
    assert projected.narrative.confidence.statement.text == (
        legacy.narrative.confidence.statement.text
    )


async def test_canonical_payload_and_explanation_remain_unchanged() -> None:
    """Cutover validation confirms the facade embeds exact canonical structures."""
    business_id = uuid.uuid4()
    supplied = canonical_input(business_id)
    migration, _, _, _ = facade(value=supplied)

    projected = await migration.get_brief(
        BusinessBriefRequest(
            business_id=business_id,
            user_id=uuid.uuid4(),
            as_of=AS_OF,
        )
    )

    assert projected.canonical_brief is not None
    assert projected.canonical_brief.narrative_items is supplied.narrative_items
    assert projected.canonical_brief.recommendations is supplied.recommendations
    assert projected.canonical_brief.limitations is supplied.limitations
    assert projected.canonical_explanation is not None
    assert projected.canonical_explanation.brief is projected.canonical_brief
    assert projected.canonical_explanation.narrative_items is supplied.narrative_items


async def test_audit_and_business_isolation_match_es001_boundary() -> None:
    """Authorized retrieval audits the response and rejects another business."""
    business_id = uuid.uuid4()
    supplied = canonical_input(business_id)
    audit = FakeAuditRepository()
    migration, _, _, _ = facade(value=supplied, audit=audit)

    projected = await migration.get_brief(
        BusinessBriefRequest(
            business_id=business_id,
            user_id=uuid.uuid4(),
            as_of=AS_OF,
        )
    )

    assert audit.recorded == [projected]
    with pytest.raises(BusinessBriefSourceMismatchError, match="Canonical Brief input"):
        await migration.get_brief(
            BusinessBriefRequest(
                business_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                as_of=AS_OF,
            )
        )


async def test_temporal_validation_matches_the_requested_es001_point_in_time() -> None:
    """A canonical input for another time cannot be projected through the facade."""
    business_id = uuid.uuid4()
    supplied = canonical_input(business_id)
    migration, _, _, _ = facade(value=supplied)

    with pytest.raises(BusinessBriefSourceMismatchError, match="point in time"):
        await migration.get_brief(
            BusinessBriefRequest(
                business_id=business_id,
                user_id=uuid.uuid4(),
                as_of=AS_OF.replace(hour=8),
            )
        )


async def test_legacy_route_remains_operational_as_cutover_rollback() -> None:
    """The characterized ES-001 route remains callable independently of the facade."""
    business_id = uuid.uuid4()
    result = await make_service(business_id=business_id).get_brief(
        BusinessBriefRequest(
            business_id=business_id,
            user_id=uuid.uuid4(),
            as_of=AS_OF,
        )
    )

    assert result.canonical_brief is None
    assert result.projection_status is None


async def test_projection_unavailable_retains_canonical_payload() -> None:
    """ES-007A requires unavailable aliases to remain explicit without fallback."""
    business_id = uuid.uuid4()
    supplied = canonical_input(business_id)
    original = descriptor(supplied)
    invalid_item = item(BusinessBriefSourceKind.BUSINESS_HEALTH, "outside-health")
    unavailable = replace(
        original,
        health=replace(
            original.health,
            narrative_item=invalid_item,
            source_reference=invalid_item.source_references[0],
        ),
    )
    migration, _, _, _ = facade(value=supplied, projection=unavailable)

    projected = await migration.get_brief(
        BusinessBriefRequest(
            business_id=business_id,
            user_id=uuid.uuid4(),
            as_of=AS_OF,
        )
    )

    assert projected.projection_status == "unavailable"
    assert projected.canonical_brief is not None
    assert projected.projection_limitations
