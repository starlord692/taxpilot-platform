"""Unit tests for the ES-001 Business Brief application boundary."""

import uuid
from datetime import UTC, datetime

import pytest

from app.modules.business_brief.exceptions import (
    BusinessBriefAccessDeniedError,
    BusinessBriefSourceMismatchError,
)
from app.modules.business_brief.models import (
    BriefItem,
    BriefItemKind,
    BusinessBrief,
    BusinessBriefContext,
    BusinessBriefRequest,
    CanonicalSignal,
    EvidenceReference,
    NarrativeStatement,
    SignalKind,
)
from app.modules.business_brief.service import BusinessBriefService

pytestmark = pytest.mark.asyncio

AS_OF = datetime(2026, 8, 4, 9, 0, tzinfo=UTC)


def statement(text: str) -> NarrativeStatement:
    """Build a traceable deterministic statement for tests."""
    return NarrativeStatement(
        text=text,
        evidence=(
            EvidenceReference(
                source="deterministic-business-record",
                reference="record-1",
                description="Test evidence",
            ),
        ),
    )


class FakeAuthorization:
    """Configurable access-policy fake."""

    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed

    async def can_access(self, *, business_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Return configured authorization result."""
        _ = business_id, user_id
        return self.allowed


class FakeContextProvider:
    """Returns a configured approved business context."""

    def __init__(self, context: BusinessBriefContext) -> None:
        self.context = context

    async def get_context(
        self,
        *,
        business_id: uuid.UUID,
        as_of: datetime,
    ) -> BusinessBriefContext:
        """Return the configured context."""
        _ = business_id, as_of
        return self.context


class FakeHealthReader:
    """Returns a configured canonical Health snapshot."""

    def __init__(self, signal: CanonicalSignal) -> None:
        self.signal = signal

    async def get_health(
        self,
        *,
        business_id: uuid.UUID,
        as_of: datetime,
    ) -> CanonicalSignal:
        """Return the configured snapshot."""
        _ = business_id, as_of
        return self.signal


class FakeMomentumReader:
    """Returns a configured canonical Momentum snapshot."""

    def __init__(self, signal: CanonicalSignal) -> None:
        self.signal = signal

    async def get_momentum(
        self,
        *,
        business_id: uuid.UUID,
        as_of: datetime,
    ) -> CanonicalSignal:
        """Return the configured snapshot."""
        _ = business_id, as_of
        return self.signal


class FakeConfidenceReader:
    """Returns a configured canonical Confidence snapshot."""

    def __init__(self, signal: CanonicalSignal) -> None:
        self.signal = signal

    async def get_confidence(
        self,
        *,
        business_id: uuid.UUID,
        as_of: datetime,
    ) -> CanonicalSignal:
        """Return the configured snapshot."""
        _ = business_id, as_of
        return self.signal


class FakeMaterialReader:
    """Returns configured material items for narrative integration."""

    def __init__(self, items: tuple[BriefItem, ...]) -> None:
        self.items = items

    async def list_material_items(
        self,
        *,
        business_id: uuid.UUID,
        as_of: datetime,
    ) -> tuple[BriefItem, ...]:
        """Return configured material items."""
        _ = business_id, as_of
        return self.items


class FakeAuditRepository:
    """Records Brief retrievals in memory."""

    def __init__(self) -> None:
        self.recorded: list[BusinessBrief] = []

    async def record_retrieval(self, brief: BusinessBrief) -> None:
        """Record the supplied Brief."""
        self.recorded.append(brief)


def make_service(
    *,
    business_id: uuid.UUID,
    allowed: bool = True,
    health_kind: SignalKind = SignalKind.HEALTH,
    audit_repository: FakeAuditRepository | None = None,
) -> BusinessBriefService:
    """Create a service wired only to controlled boundary fakes."""
    context = BusinessBriefContext(
        business_id=business_id,
        current_understanding=statement("Business activity requires attention."),
        business_dna=(EvidenceReference("business-dna", "dna-1", "Retail business"),),
    )
    return BusinessBriefService(
        authorization=FakeAuthorization(allowed),
        context_provider=FakeContextProvider(context),
        health_reader=FakeHealthReader(
            CanonicalSignal(
                kind=health_kind,
                statement=statement("Current condition is healthy."),
                assessed_at=AS_OF,
            )
        ),
        momentum_reader=FakeMomentumReader(
            CanonicalSignal(
                kind=SignalKind.MOMENTUM,
                statement=statement("Observed movement is improving."),
                assessed_at=AS_OF,
            )
        ),
        confidence_reader=FakeConfidenceReader(
            CanonicalSignal(
                kind=SignalKind.CONFIDENCE,
                statement=statement("Understanding is reliable with stated limits."),
                assessed_at=AS_OF,
            )
        ),
        material_reader=FakeMaterialReader(
            (
                BriefItem(
                    kind=BriefItemKind.PRIORITY,
                    statement=statement("Review an overdue receivable."),
                    requires_owner_approval=True,
                ),
            )
        ),
        audit_repository=audit_repository,
    )


async def test_get_brief_integrates_authoritative_inputs_without_redefining_them() -> (
    None
):
    """The boundary preserves source signal identities and supporting evidence."""
    business_id = uuid.uuid4()
    user_id = uuid.uuid4()
    audit = FakeAuditRepository()
    service = make_service(business_id=business_id, audit_repository=audit)

    brief = await service.get_brief(
        BusinessBriefRequest(business_id=business_id, user_id=user_id, as_of=AS_OF)
    )

    assert brief.business_id == business_id
    assert brief.context is not None
    assert brief.narrative is not None
    assert brief.requested_by == user_id
    assert brief.narrative.health.kind is SignalKind.HEALTH
    assert brief.narrative.momentum.kind is SignalKind.MOMENTUM
    assert brief.narrative.confidence.kind is SignalKind.CONFIDENCE
    assert brief.narrative.health.statement.evidence
    assert brief.context.business_dna
    assert brief.narrative.material_items[0].requires_owner_approval is True
    assert audit.recorded == [brief]


async def test_get_brief_denies_unauthorized_business_access() -> None:
    """The boundary does not expose a Brief outside the authorized business context."""
    business_id = uuid.uuid4()
    service = make_service(business_id=business_id, allowed=False)

    with pytest.raises(BusinessBriefAccessDeniedError):
        await service.get_brief(
            BusinessBriefRequest(
                business_id=business_id,
                user_id=uuid.uuid4(),
                as_of=AS_OF,
            )
        )


async def test_get_brief_rejects_a_conflated_canonical_signal() -> None:
    """The boundary rejects a source that attempts to use Momentum as Health."""
    business_id = uuid.uuid4()
    service = make_service(
        business_id=business_id,
        health_kind=SignalKind.MOMENTUM,
    )

    with pytest.raises(BusinessBriefSourceMismatchError, match="business_health"):
        await service.get_brief(
            BusinessBriefRequest(
                business_id=business_id,
                user_id=uuid.uuid4(),
                as_of=AS_OF,
            )
        )
