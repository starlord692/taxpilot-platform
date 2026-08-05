"""Contract tests for BRIEF-003 ES-006 Business Brief ports."""

import uuid
from dataclasses import replace

import pytest

from app.modules.business_brief.es006 import (
    BusinessBrief,
    BusinessBriefHistoryRepository,
    BusinessBriefInput,
    BusinessBriefInputProvider,
    BusinessBriefReadProvider,
    BusinessBriefRepository,
    BusinessBriefService,
    BusinessBriefSourceRepository,
    BusinessBriefTraceability,
    BusinessBriefTraceabilityRepository,
)
from tests.test_business_brief_es006_service import brief_input


class FakeSourceRepository:
    """In-memory authoritative-input repository contract fake."""

    def __init__(self, value: BusinessBriefInput) -> None:
        self.value = value

    async def get_brief_input(
        self, *, business_id: object, brief_at: object
    ) -> BusinessBriefInput:
        """Return configured authoritative input for its matching request."""
        assert business_id == self.value.business_id
        assert brief_at == self.value.brief_at
        return self.value


class FakeBriefRepository:
    """In-memory authoritative-Brief repository contract fake."""

    def __init__(self, value: BusinessBrief) -> None:
        self.value = value

    async def get_at(
        self, *, business_id: object, brief_at: object
    ) -> BusinessBrief | None:
        """Return the configured Brief only for its matching identity and time."""
        if business_id == self.value.business_id and brief_at == self.value.brief_at:
            return self.value
        return None

    async def get_latest(self, *, business_id: object) -> BusinessBrief | None:
        """Return the configured latest Brief only for its matching business."""
        return self.value if business_id == self.value.business_id else None


class FakeHistoryRepository:
    """In-memory authoritative-Brief history repository contract fake."""

    def __init__(self, values: tuple[BusinessBrief, ...]) -> None:
        self.values = values

    async def get_history(self, *, business_id: object) -> tuple[BusinessBrief, ...]:
        """Return configured Briefs only for the requested business."""
        return tuple(value for value in self.values if value.business_id == business_id)


class FakeTraceabilityRepository:
    """In-memory authoritative-traceability repository contract fake."""

    def __init__(self, value: BusinessBriefTraceability) -> None:
        self.value = value

    async def get_traceability(
        self, *, business_id: object, brief_at: object
    ) -> BusinessBriefTraceability | None:
        """Return traceability only for its matching Brief identity and time."""
        if business_id == self.value.business_id and brief_at == self.value.brief_at:
            return self.value
        return None


class FakeInputProvider:
    """In-memory authoritative-input provider contract fake."""

    def __init__(self, value: BusinessBriefInput) -> None:
        self.value = value

    async def provide_input(
        self, *, business_id: object, brief_at: object
    ) -> BusinessBriefInput:
        """Return configured input without generating or selecting Brief content."""
        assert business_id == self.value.business_id
        assert brief_at == self.value.brief_at
        return self.value


class FakeReadProvider:
    """In-memory approved-consumer read-provider contract fake."""

    def __init__(self, value: BusinessBrief) -> None:
        self.value = value

    async def get_current(
        self, *, business_id: object, brief_at: object
    ) -> BusinessBrief | None:
        """Return configured Brief only for its matching business and point in time."""
        if business_id == self.value.business_id and brief_at == self.value.brief_at:
            return self.value
        return None


def assembled_brief() -> BusinessBrief:
    """Build immutable output directly from supplied authoritative structures."""
    return BusinessBriefService().assemble(brief_input())


def traceability(value: BusinessBrief) -> BusinessBriefTraceability:
    """Preserve traceability structures from an authoritative Brief unchanged."""
    narrative = value.narrative_items[0]
    return BusinessBriefTraceability(
        business_id=value.business_id,
        brief_at=value.brief_at,
        source_references=narrative.source_references,
        evidence=narrative.evidence,
        approved_context=narrative.approved_context,
        limitations=value.limitations,
    )


@pytest.mark.asyncio
async def test_repository_contracts_are_read_only_and_technology_agnostic() -> None:
    """Repository ports are fulfilled by in-memory fakes without infrastructure."""
    supplied = brief_input()
    current = assembled_brief()
    earlier = replace(current, brief_at=current.brief_at.replace(hour=8))
    source = FakeSourceRepository(supplied)
    briefs = FakeBriefRepository(current)
    history = FakeHistoryRepository((earlier, current))
    traces = FakeTraceabilityRepository(traceability(current))

    assert isinstance(source, BusinessBriefSourceRepository)
    assert isinstance(briefs, BusinessBriefRepository)
    assert isinstance(history, BusinessBriefHistoryRepository)
    assert isinstance(traces, BusinessBriefTraceabilityRepository)
    assert (
        await source.get_brief_input(
            business_id=supplied.business_id, brief_at=supplied.brief_at
        )
        is supplied
    )
    assert (
        await briefs.get_at(business_id=current.business_id, brief_at=current.brief_at)
        is current
    )
    assert await briefs.get_latest(business_id=current.business_id) is current
    assert await history.get_history(business_id=current.business_id) == (
        earlier,
        current,
    )
    assert await traces.get_traceability(
        business_id=current.business_id, brief_at=current.brief_at
    ) == traceability(current)


@pytest.mark.asyncio
async def test_provider_contracts_preserve_authoritative_consumer_boundaries() -> None:
    """Provider ports expose supplied input and output without transformation."""
    supplied = brief_input()
    current = assembled_brief()
    input_provider = FakeInputProvider(supplied)
    read_provider = FakeReadProvider(current)

    assert isinstance(input_provider, BusinessBriefInputProvider)
    assert isinstance(read_provider, BusinessBriefReadProvider)
    assert (
        await input_provider.provide_input(
            business_id=supplied.business_id, brief_at=supplied.brief_at
        )
        is supplied
    )
    assert (
        await read_provider.get_current(
            business_id=current.business_id, brief_at=current.brief_at
        )
        is current
    )


@pytest.mark.asyncio
async def test_read_boundaries_do_not_expose_another_business() -> None:
    """Read-only ports retain business isolation for every requested structure."""
    current = assembled_brief()
    repository = FakeBriefRepository(current)
    trace_repository = FakeTraceabilityRepository(traceability(current))
    read_provider = FakeReadProvider(current)
    other_business = uuid.uuid4()

    assert await repository.get_at(
        business_id=other_business, brief_at=current.brief_at
    ) is None
    assert await repository.get_latest(business_id=other_business) is None
    assert await trace_repository.get_traceability(
        business_id=other_business, brief_at=current.brief_at
    ) is None
    assert await read_provider.get_current(
        business_id=other_business, brief_at=current.brief_at
    ) is None


def test_traceability_is_immutable_and_preserves_authoritative_structures() -> None:
    """Traceability retains exact source, evidence, context, and limitation values."""
    current = assembled_brief()
    result = traceability(current)
    narrative = current.narrative_items[0]

    assert result.source_references is narrative.source_references
    assert result.evidence is narrative.evidence
    assert result.approved_context is narrative.approved_context
    assert result.limitations is current.limitations
    with pytest.raises(AttributeError):
        result.brief_at = current.brief_at  # type: ignore[misc]


def test_contracts_are_protocol_only_dependency_boundaries() -> None:
    """Every BRIEF-003 dependency boundary is a runtime-checkable Protocol."""
    contracts = (
        BusinessBriefSourceRepository,
        BusinessBriefRepository,
        BusinessBriefHistoryRepository,
        BusinessBriefTraceabilityRepository,
        BusinessBriefInputProvider,
        BusinessBriefReadProvider,
    )

    assert all(
        getattr(contract, "_is_protocol", False) is True for contract in contracts
    )
    assert all(
        getattr(contract, "_is_runtime_protocol", False) is True
        for contract in contracts
    )