"""Focused ES-007 compatibility-facade migration tests."""

import uuid
from datetime import datetime

import pytest

from app.modules.business_brief.es006 import (
    BusinessBriefInput,
    BusinessBriefNarrativeItem,
    BusinessBriefSourceKind,
    BusinessBriefSourceReference,
)
from app.modules.business_brief.exceptions import (
    BusinessBriefAccessDeniedError,
    BusinessBriefSourceMismatchError,
)
from app.modules.business_brief.migration import (
    BusinessBriefCompatibilityContextAlias,
    BusinessBriefCompatibilityFacade,
    BusinessBriefCompatibilityProjectionDescriptor,
    BusinessBriefCompatibilitySignalAlias,
)
from app.modules.business_brief.models import BusinessBriefRequest
from tests.test_business_brief_service import AS_OF, FakeAuditRepository, make_service

pytestmark = pytest.mark.asyncio


class FakeAuthorization:
    """In-memory ES-001 authorization fake."""

    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.calls: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def can_access(self, *, business_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Record and return the configured authorization outcome."""
        self.calls.append((business_id, user_id))
        return self.allowed


class FakeCanonicalInputProvider:
    """In-memory published ES-006 input-provider fake."""

    def __init__(self, value: BusinessBriefInput) -> None:
        self.value = value
        self.calls: list[tuple[uuid.UUID, datetime]] = []

    async def provide_input(
        self, *, business_id: uuid.UUID, brief_at: datetime
    ) -> BusinessBriefInput:
        """Return the configured authoritative input unchanged."""
        self.calls.append((business_id, brief_at))
        return self.value


class FakeProjectionProvider:
    """In-memory ES-007 descriptor-provider fake."""

    def __init__(self, value: BusinessBriefCompatibilityProjectionDescriptor) -> None:
        self.value = value
        self.calls: list[tuple[uuid.UUID, datetime]] = []

    async def provide_descriptor(
        self,
        *,
        business_id: uuid.UUID,
        brief_at: datetime,
        canonical_brief: object,
    ) -> BusinessBriefCompatibilityProjectionDescriptor:
        """Return the configured migration-owned descriptor unchanged."""
        assert canonical_brief.business_id == business_id  # type: ignore[attr-defined]
        assert canonical_brief.brief_at == brief_at  # type: ignore[attr-defined]
        self.calls.append((business_id, brief_at))
        return self.value


def source(
    kind: BusinessBriefSourceKind, reference: str
) -> BusinessBriefSourceReference:
    """Build one owner-published source reference for an authoritative Brief."""
    return BusinessBriefSourceReference(
        kind=kind,
        source_owner=kind.value,
        reference=reference,
        description=f"Authoritative {kind.value} source",
        effective_at=AS_OF,
        limitations=("Available understanding remains bounded",),
    )


def item(kind: BusinessBriefSourceKind, reference: str) -> BusinessBriefNarrativeItem:
    """Build one supplied canonical narrative item with direct source ownership."""
    return BusinessBriefNarrativeItem(
        statement=f"Authoritative {kind.value} statement.",
        source_references=(source(kind, reference),),
        limitations=("Available understanding remains bounded",),
    )


def canonical_input(business_id: uuid.UUID) -> BusinessBriefInput:
    """Build supplied ES-006 input without selection or generated content."""
    return BusinessBriefInput(
        business_id=business_id,
        brief_at=AS_OF,
        narrative_items=(
            item(BusinessBriefSourceKind.BUSINESS_DNA, "dna-1"),
            item(BusinessBriefSourceKind.BUSINESS_HEALTH, "health-1"),
            item(BusinessBriefSourceKind.BUSINESS_MOMENTUM, "momentum-1"),
            item(BusinessBriefSourceKind.BUSINESS_CONFIDENCE, "confidence-1"),
        ),
        limitations=("Available understanding remains bounded",),
    )


def descriptor(
    value: BusinessBriefInput,
    *,
    business_id: uuid.UUID | None = None,
) -> BusinessBriefCompatibilityProjectionDescriptor:
    """Declare exact canonical correspondences without selecting alternatives."""
    dna, health, momentum, confidence = value.narrative_items
    return BusinessBriefCompatibilityProjectionDescriptor(
        business_id=business_id or value.business_id,
        brief_at=value.brief_at,
        context=BusinessBriefCompatibilityContextAlias(
            current_understanding=dna,
            business_dna=dna.source_references,
        ),
        health=BusinessBriefCompatibilitySignalAlias(
            narrative_item=health,
            source_reference=health.source_references[0],
        ),
        momentum=BusinessBriefCompatibilitySignalAlias(
            narrative_item=momentum,
            source_reference=momentum.source_references[0],
        ),
        confidence=BusinessBriefCompatibilitySignalAlias(
            narrative_item=confidence,
            source_reference=confidence.source_references[0],
        ),
    )


def facade(
    *,
    value: BusinessBriefInput,
    allowed: bool = True,
    projection: BusinessBriefCompatibilityProjectionDescriptor | None = None,
    audit: FakeAuditRepository | None = None,
) -> tuple[
    BusinessBriefCompatibilityFacade,
    FakeAuthorization,
    FakeCanonicalInputProvider,
    FakeProjectionProvider,
]:
    """Build the temporary facade with in-memory contract implementations."""
    authorization = FakeAuthorization(allowed)
    input_provider = FakeCanonicalInputProvider(value)
    projection_provider = FakeProjectionProvider(projection or descriptor(value))
    return (
        BusinessBriefCompatibilityFacade(
            authorization=authorization,
            canonical_input_provider=input_provider,
            projection_provider=projection_provider,
            audit_repository=audit,
        ),
        authorization,
        input_provider,
        projection_provider,
    )


async def test_facade_translates_es001_request_to_canonical_input_and_response() -> (
    None
):
    """The facade preserves legacy request semantics and embeds canonical output."""
    business_id = uuid.uuid4()
    user_id = uuid.uuid4()
    supplied = canonical_input(business_id)
    audit = FakeAuditRepository()
    service, authorization, input_provider, projection_provider = facade(
        value=supplied,
        audit=audit,
    )

    result = await service.get_brief(
        BusinessBriefRequest(business_id=business_id, user_id=user_id, as_of=AS_OF)
    )

    assert authorization.calls == [(business_id, user_id)]
    assert input_provider.calls == [(business_id, AS_OF)]
    assert projection_provider.calls == [(business_id, AS_OF)]
    assert result.business_id == business_id
    assert result.requested_by == user_id
    assert result.as_of == AS_OF
    assert result.canonical_brief is not None
    assert result.canonical_brief.narrative_items is supplied.narrative_items
    assert result.canonical_explanation is not None
    assert result.canonical_explanation.brief is result.canonical_brief
    assert result.projection_status == "available"
    assert result.projection_limitations is supplied.limitations
    assert result.narrative.health.kind.value == "business_health"
    assert result.narrative.momentum.kind.value == "business_momentum"
    assert result.narrative.confidence.kind.value == "business_confidence"
    assert audit.recorded == [result]


async def test_facade_preserves_alias_traceability_and_temporal_context() -> None:
    """Every exposed alias points to supplied canonical source structures only."""
    business_id = uuid.uuid4()
    supplied = canonical_input(business_id)
    service, _, _, _ = facade(value=supplied)

    result = await service.get_brief(
        BusinessBriefRequest(
            business_id=business_id,
            user_id=uuid.uuid4(),
            as_of=AS_OF,
        )
    )

    assert result.context.business_id == business_id
    assert (
        result.context.current_understanding.text
        == supplied.narrative_items[0].statement
    )
    assert result.context.business_dna[0].source == "business_dna"
    assert result.narrative.health.assessed_at == AS_OF
    assert result.canonical_brief is not None
    assert (
        result.canonical_brief.narrative_items[1].source_references[0].effective_at
        == AS_OF
    )
    assert result.canonical_brief.limitations == result.projection_limitations


async def test_facade_rejects_unauthorized_request_before_canonical_retrieval() -> None:
    """Authorization and business isolation precede canonical capability access."""
    business_id = uuid.uuid4()
    supplied = canonical_input(business_id)
    service, _, input_provider, projection_provider = facade(
        value=supplied, allowed=False
    )

    with pytest.raises(BusinessBriefAccessDeniedError):
        await service.get_brief(
            BusinessBriefRequest(
                business_id=business_id,
                user_id=uuid.uuid4(),
                as_of=AS_OF,
            )
        )

    assert input_provider.calls == []
    assert projection_provider.calls == []


async def test_facade_rejects_cross_business_canonical_input() -> None:
    """The facade cannot expose canonical output from another business."""
    requested_business = uuid.uuid4()
    service, _, _, _ = facade(value=canonical_input(uuid.uuid4()))

    with pytest.raises(ValueError, match="Canonical Brief input does not match"):
        await service.get_brief(
            BusinessBriefRequest(
                business_id=requested_business,
                user_id=uuid.uuid4(),
                as_of=AS_OF,
            )
        )


async def test_facade_rejects_untraceable_descriptor_reference() -> None:
    """The facade does not choose a replacement for an invalid legacy alias."""
    business_id = uuid.uuid4()
    supplied = canonical_input(business_id)
    unrelated = item(BusinessBriefSourceKind.BUSINESS_HEALTH, "health-outside")
    invalid = BusinessBriefCompatibilityProjectionDescriptor(
        business_id=business_id,
        brief_at=AS_OF,
        context=descriptor(supplied).context,
        health=BusinessBriefCompatibilitySignalAlias(
            narrative_item=unrelated,
            source_reference=unrelated.source_references[0],
        ),
        momentum=descriptor(supplied).momentum,
        confidence=descriptor(supplied).confidence,
    )
    service, _, _, _ = facade(value=supplied, projection=invalid)

    with pytest.raises(BusinessBriefSourceMismatchError, match="not present"):
        await service.get_brief(
            BusinessBriefRequest(
                business_id=business_id,
                user_id=uuid.uuid4(),
                as_of=AS_OF,
            )
        )


async def test_characterized_legacy_route_remains_available_for_rollback() -> None:
    """The facade does not replace or mutate the original ES-001 service route."""
    business_id = uuid.uuid4()
    legacy_service = make_service(business_id=business_id)

    result = await legacy_service.get_brief(
        BusinessBriefRequest(
            business_id=business_id,
            user_id=uuid.uuid4(),
            as_of=AS_OF,
        )
    )

    assert result.canonical_brief is None
    assert result.projection_status is None
