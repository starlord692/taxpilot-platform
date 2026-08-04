"""Contract tests for DNA-003 Business DNA repository and provider ports."""

from dataclasses import replace
from datetime import timedelta

import pytest

from app.modules.business_dna import (
    BusinessDNAContext,
    BusinessDNAContextInput,
    BusinessDNAContextRepository,
    BusinessDNAInputProvider,
    BusinessDNAReadProvider,
    BusinessDNARevisionHistoryRepository,
    BusinessDNASourceRepository,
    BusinessDNATraceability,
    BusinessDNATraceabilityRepository,
)
from tests.test_business_dna_service import input_context

pytestmark = pytest.mark.asyncio


class FakeSourceRepository:
    """In-memory source repository contract fake."""

    def __init__(self, value: BusinessDNAContextInput) -> None:
        self.value = value

    async def get_context_input(
        self,
        *,
        business_id: object,
        recorded_at: object,
    ) -> BusinessDNAContextInput:
        """Return configured authoritative input."""
        assert business_id == self.value.business_id
        assert recorded_at == self.value.recorded_at
        return self.value


class FakeContextRepository:
    """In-memory context repository contract fake."""

    def __init__(self, value: BusinessDNAContext) -> None:
        self.value = value

    async def get_at(
        self,
        *,
        business_id: object,
        recorded_at: object,
    ) -> BusinessDNAContext | None:
        """Return configured context for a matching request."""
        if (
            business_id == self.value.business_id
            and recorded_at == self.value.recorded_at
        ):
            return self.value
        return None

    async def get_latest(self, *, business_id: object) -> BusinessDNAContext | None:
        """Return configured latest context for a matching business."""
        return self.value if business_id == self.value.business_id else None


class FakeRevisionHistoryRepository:
    """In-memory revision-history repository contract fake."""

    def __init__(self, values: tuple[BusinessDNAContext, ...]) -> None:
        self.values = values

    async def get_revision_history(
        self,
        *,
        business_id: object,
    ) -> tuple[BusinessDNAContext, ...]:
        """Return configured authoritative revision history."""
        return tuple(value for value in self.values if value.business_id == business_id)


class FakeTraceabilityRepository:
    """In-memory provenance and traceability repository contract fake."""

    def __init__(self, value: BusinessDNATraceability) -> None:
        self.value = value

    async def get_traceability(
        self,
        *,
        business_id: object,
        revision: object,
    ) -> BusinessDNATraceability | None:
        """Return configured traceability for a matching revision."""
        if business_id == self.value.business_id and revision == self.value.revision:
            return self.value
        return None


class FakeInputProvider:
    """In-memory authoritative-input provider contract fake."""

    def __init__(self, value: BusinessDNAContextInput) -> None:
        self.value = value

    async def provide_input(
        self,
        *,
        business_id: object,
        recorded_at: object,
    ) -> BusinessDNAContextInput:
        """Return configured descriptive input."""
        assert business_id == self.value.business_id
        assert recorded_at == self.value.recorded_at
        return self.value


class FakeReadProvider:
    """In-memory approved-consumer read-provider contract fake."""

    def __init__(self, value: BusinessDNAContext) -> None:
        self.value = value

    async def get_current(
        self,
        *,
        business_id: object,
        recorded_at: object,
    ) -> BusinessDNAContext | None:
        """Return configured context for an approved matching request."""
        if (
            business_id == self.value.business_id
            and recorded_at == self.value.recorded_at
        ):
            return self.value
        return None


def assembled_context() -> BusinessDNAContext:
    """Build a complete immutable context without using an adapter."""
    supplied = input_context()
    return BusinessDNAContext(
        business_id=supplied.business_id,
        revision=supplied.revision,
        recorded_at=supplied.recorded_at,
        identity=supplied.identity,
        operational=supplied.operational,
        financial=supplied.financial,
        compliance=supplied.compliance,
        strategic=supplied.strategic,
    )


def traceability(value: BusinessDNAContext) -> BusinessDNATraceability:
    """Build profile-level traceability directly from immutable context."""
    return BusinessDNATraceability(
        business_id=value.business_id,
        revision=value.revision,
        recorded_at=value.recorded_at,
        identity=value.identity.provenance,
        operational=value.operational.provenance,
        financial=value.financial.provenance,
        compliance=value.compliance.provenance,
        strategic=value.strategic.provenance,
    )


async def test_repository_contracts_are_read_only_and_technology_agnostic() -> None:
    """Repository ports can be fulfilled without storage or framework code."""
    supplied = input_context()
    current = assembled_context()
    earlier = replace(
        current, revision=2, recorded_at=current.recorded_at + timedelta(days=1)
    )
    source = FakeSourceRepository(supplied)
    contexts = FakeContextRepository(current)
    history = FakeRevisionHistoryRepository((current, earlier))
    traces = FakeTraceabilityRepository(traceability(current))

    assert isinstance(source, BusinessDNASourceRepository)
    assert isinstance(contexts, BusinessDNAContextRepository)
    assert isinstance(history, BusinessDNARevisionHistoryRepository)
    assert isinstance(traces, BusinessDNATraceabilityRepository)
    assert (
        await source.get_context_input(
            business_id=supplied.business_id,
            recorded_at=supplied.recorded_at,
        )
        is supplied
    )
    assert (
        await contexts.get_at(
            business_id=current.business_id,
            recorded_at=current.recorded_at,
        )
        is current
    )
    assert await contexts.get_latest(business_id=current.business_id) is current
    assert await history.get_revision_history(business_id=current.business_id) == (
        current,
        earlier,
    )
    assert await traces.get_traceability(
        business_id=current.business_id,
        revision=current.revision,
    ) == traceability(current)


async def test_provider_contracts_preserve_authoritative_consumer_boundaries() -> None:
    """Providers expose only supplied authoritative inputs and context."""
    supplied = input_context()
    current = assembled_context()
    input_provider = FakeInputProvider(supplied)
    read_provider = FakeReadProvider(current)

    assert isinstance(input_provider, BusinessDNAInputProvider)
    assert isinstance(read_provider, BusinessDNAReadProvider)
    assert (
        await input_provider.provide_input(
            business_id=supplied.business_id,
            recorded_at=supplied.recorded_at,
        )
        is supplied
    )
    assert (
        await read_provider.get_current(
            business_id=current.business_id,
            recorded_at=current.recorded_at,
        )
        is current
    )
