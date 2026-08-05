"""Contract tests for CONF-003 Business Confidence repository and provider ports."""

import uuid

import pytest

from app.modules.business_confidence import (
    BusinessConfidenceAssessment,
    BusinessConfidenceAssessmentInput,
    BusinessConfidenceAssessmentRepository,
    BusinessConfidenceInputProvider,
    BusinessConfidenceReadProvider,
    BusinessConfidenceService,
    BusinessConfidenceSourceRepository,
    BusinessConfidenceTraceability,
    BusinessConfidenceTraceabilityRepository,
)
from tests.test_business_confidence_service import assessment_input

pytestmark = pytest.mark.asyncio


class FakeSourceRepository:
    """In-memory authoritative-input repository contract fake."""

    def __init__(self, value: BusinessConfidenceAssessmentInput) -> None:
        self.value = value

    async def get_assessment_input(
        self,
        *,
        business_id: object,
        assessed_at: object,
    ) -> BusinessConfidenceAssessmentInput:
        """Return configured authoritative input for its matching request."""
        assert business_id == self.value.business_id
        assert assessed_at == self.value.assessed_at
        return self.value


class FakeAssessmentRepository:
    """In-memory authoritative-assessment repository contract fake."""

    def __init__(self, value: BusinessConfidenceAssessment) -> None:
        self.value = value

    async def get_at(
        self,
        *,
        business_id: object,
        assessed_at: object,
    ) -> BusinessConfidenceAssessment | None:
        """Return configured assessment when its identity and time match."""
        if (
            business_id == self.value.business_id
            and assessed_at == self.value.assessed_at
        ):
            return self.value
        return None

    async def get_latest(
        self,
        *,
        business_id: object,
    ) -> BusinessConfidenceAssessment | None:
        """Return configured latest assessment for its matching business."""
        return self.value if business_id == self.value.business_id else None


class FakeTraceabilityRepository:
    """In-memory deterministic-traceability repository contract fake."""

    def __init__(self, value: BusinessConfidenceTraceability) -> None:
        self.value = value

    async def get_traceability(
        self,
        *,
        business_id: object,
        assessed_at: object,
    ) -> BusinessConfidenceTraceability | None:
        """Return configured traceability when identity and time match."""
        if (
            business_id == self.value.business_id
            and assessed_at == self.value.assessed_at
        ):
            return self.value
        return None


class FakeInputProvider:
    """In-memory authoritative-input provider contract fake."""

    def __init__(self, value: BusinessConfidenceAssessmentInput) -> None:
        self.value = value

    async def provide_input(
        self,
        *,
        business_id: object,
        assessed_at: object,
    ) -> BusinessConfidenceAssessmentInput:
        """Return configured input without deriving a confidence result."""
        assert business_id == self.value.business_id
        assert assessed_at == self.value.assessed_at
        return self.value


class FakeReadProvider:
    """In-memory approved-consumer read-provider contract fake."""

    def __init__(self, value: BusinessConfidenceAssessment) -> None:
        self.value = value

    async def get_current(
        self,
        *,
        business_id: object,
        assessed_at: object,
    ) -> BusinessConfidenceAssessment | None:
        """Return configured authoritative output for a matching request."""
        if (
            business_id == self.value.business_id
            and assessed_at == self.value.assessed_at
        ):
            return self.value
        return None


def assembled_assessment() -> BusinessConfidenceAssessment:
    """Build immutable authoritative output without an adapter or repository."""
    return BusinessConfidenceService().assemble(assessment_input())


def traceability(
    value: BusinessConfidenceAssessment,
) -> BusinessConfidenceTraceability:
    """Build traceability directly from authoritative Confidence output."""
    return BusinessConfidenceTraceability(
        business_id=value.business_id,
        assessed_at=value.assessed_at,
        coverage=value.coverage,
        approved_context=value.approved_context,
        limitations=value.limitations,
    )


async def test_repository_contracts_are_read_only_and_technology_agnostic() -> None:
    """Repository ports are fulfilled without adapters, storage, or frameworks."""
    supplied = assessment_input()
    current = assembled_assessment()
    source = FakeSourceRepository(supplied)
    assessments = FakeAssessmentRepository(current)
    traces = FakeTraceabilityRepository(traceability(current))

    assert isinstance(source, BusinessConfidenceSourceRepository)
    assert isinstance(assessments, BusinessConfidenceAssessmentRepository)
    assert isinstance(traces, BusinessConfidenceTraceabilityRepository)
    assert (
        await source.get_assessment_input(
            business_id=supplied.business_id,
            assessed_at=supplied.assessed_at,
        )
        is supplied
    )
    assert (
        await assessments.get_at(
            business_id=current.business_id,
            assessed_at=current.assessed_at,
        )
        is current
    )
    assert await assessments.get_latest(business_id=current.business_id) is current
    assert await traces.get_traceability(
        business_id=current.business_id,
        assessed_at=current.assessed_at,
    ) == traceability(current)


async def test_provider_contracts_preserve_authoritative_consumer_boundaries() -> None:
    """Provider ports expose supplied inputs and output without recalculation."""
    supplied = assessment_input()
    current = assembled_assessment()
    input_provider = FakeInputProvider(supplied)
    read_provider = FakeReadProvider(current)

    assert isinstance(input_provider, BusinessConfidenceInputProvider)
    assert isinstance(read_provider, BusinessConfidenceReadProvider)
    assert (
        await input_provider.provide_input(
            business_id=supplied.business_id,
            assessed_at=supplied.assessed_at,
        )
        is supplied
    )
    assert (
        await read_provider.get_current(
            business_id=current.business_id,
            assessed_at=current.assessed_at,
        )
        is current
    )


async def test_assessment_repository_is_scoped_to_requested_business() -> None:
    """Read-only retrieval never exposes an assessment for another business."""
    current = assembled_assessment()
    repository = FakeAssessmentRepository(current)

    assert await repository.get_at(
        business_id=uuid.uuid4(),
        assessed_at=current.assessed_at,
    ) is None
    assert await repository.get_latest(business_id=uuid.uuid4()) is None
