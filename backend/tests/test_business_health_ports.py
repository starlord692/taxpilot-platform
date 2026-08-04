"""Contract tests for BH-003 Business Health repository and provider ports."""

import uuid
from datetime import UTC, datetime

import pytest

from app.modules.business_health.models import (
    BusinessHealthAssessment,
    DeterministicEvidenceReference,
    HealthDimension,
    HealthDimensionEvidence,
    HealthState,
)
from app.modules.business_health.ports import (
    BusinessHealthAssessmentRepository,
    BusinessHealthInputProvider,
    BusinessHealthReadProvider,
    BusinessHealthSourceRepository,
    BusinessHealthTraceability,
    BusinessHealthTraceabilityRepository,
)
from app.modules.business_health.service import (
    BusinessHealthAssessmentInput,
    HealthDimensionInput,
)

pytestmark = pytest.mark.asyncio

ASSESSED_AT = datetime(2026, 8, 5, 11, 0, tzinfo=UTC)


def evidence(dimension: HealthDimension) -> DeterministicEvidenceReference:
    """Create deterministic evidence for a contract fake."""
    return DeterministicEvidenceReference(
        source=f"{dimension.value}-domain",
        reference=f"{dimension.value}-record",
        description=f"Verified {dimension.value} information",
    )


def dimension_evidence() -> tuple[HealthDimensionEvidence, ...]:
    """Create evidence for all canonical dimensions without calculating Health."""
    return tuple(
        HealthDimensionEvidence(
            dimension=dimension,
            evidence=(evidence(dimension),),
        )
        for dimension in HealthDimension
    )


def assessment_input(business_id: uuid.UUID) -> BusinessHealthAssessmentInput:
    """Create an authoritative input shape for contract tests."""

    return BusinessHealthAssessmentInput(
        business_id=business_id,
        assessed_at=ASSESSED_AT,
        dimensions=tuple(
            HealthDimensionInput(
                dimension=item.dimension,
                state=HealthState.HEALTHY,
                evidence=item,
                contributors=(),
            )
            for item in dimension_evidence()
        ),
    )


def assessment(business_id: uuid.UUID) -> BusinessHealthAssessment:
    """Create an authoritative Health output shape for contract tests."""
    return BusinessHealthAssessment(
        business_id=business_id,
        assessed_at=ASSESSED_AT,
        state=HealthState.HEALTHY,
        dimension_evidence=dimension_evidence(),
        contributors=(),
    )


class FakeSourceRepository:
    """In-memory source repository contract fake."""

    def __init__(self, value: BusinessHealthAssessmentInput) -> None:
        self.value = value

    async def get_assessment_input(
        self,
        *,
        business_id: uuid.UUID,
        assessed_at: datetime,
    ) -> BusinessHealthAssessmentInput:
        """Return configured canonical input."""
        assert business_id == self.value.business_id
        assert assessed_at == self.value.assessed_at
        return self.value


class FakeAssessmentRepository:
    """In-memory assessment repository contract fake."""

    def __init__(self, value: BusinessHealthAssessment) -> None:
        self.value = value

    async def get_at(
        self,
        *,
        business_id: uuid.UUID,
        assessed_at: datetime,
    ) -> BusinessHealthAssessment | None:
        """Return the configured assessment for a matching request."""
        if (
            business_id == self.value.business_id
            and assessed_at == self.value.assessed_at
        ):
            return self.value
        return None

    async def get_latest(
        self,
        *,
        business_id: uuid.UUID,
    ) -> BusinessHealthAssessment | None:
        """Return the configured latest assessment for a matching business."""
        return self.value if business_id == self.value.business_id else None


class FakeTraceabilityRepository:
    """In-memory traceability repository contract fake."""

    def __init__(self, value: BusinessHealthTraceability) -> None:
        self.value = value

    async def get_traceability(
        self,
        *,
        business_id: uuid.UUID,
        assessed_at: datetime,
    ) -> BusinessHealthTraceability | None:
        """Return the configured traceability for a matching request."""
        if (
            business_id == self.value.business_id
            and assessed_at == self.value.assessed_at
        ):
            return self.value
        return None


class FakeInputProvider:
    """In-memory read-provider contract fake."""

    def __init__(self, value: BusinessHealthAssessmentInput) -> None:
        self.value = value

    async def provide_input(
        self,
        *,
        business_id: uuid.UUID,
        assessed_at: datetime,
    ) -> BusinessHealthAssessmentInput:
        """Return configured canonical input."""
        assert business_id == self.value.business_id
        assert assessed_at == self.value.assessed_at
        return self.value


class FakeReadProvider:
    """In-memory authoritative-output provider contract fake."""

    def __init__(self, value: BusinessHealthAssessment) -> None:
        self.value = value

    async def get_current(
        self,
        *,
        business_id: uuid.UUID,
        assessed_at: datetime,
    ) -> BusinessHealthAssessment | None:
        """Return configured authoritative output for a matching request."""
        if (
            business_id == self.value.business_id
            and assessed_at == self.value.assessed_at
        ):
            return self.value
        return None


async def test_repository_contracts_are_technology_agnostic_and_read_only() -> None:
    """Repository ports can be satisfied without storage or infrastructure code."""
    business_id = uuid.uuid4()
    source = FakeSourceRepository(assessment_input(business_id))
    health = assessment(business_id)
    assessments = FakeAssessmentRepository(health)
    traceability = BusinessHealthTraceability(
        business_id=business_id,
        assessed_at=ASSESSED_AT,
        dimension_evidence=health.dimension_evidence,
        contributors=(),
    )
    traces = FakeTraceabilityRepository(traceability)

    assert isinstance(source, BusinessHealthSourceRepository)
    assert isinstance(assessments, BusinessHealthAssessmentRepository)
    assert isinstance(traces, BusinessHealthTraceabilityRepository)
    assert await source.get_assessment_input(
        business_id=business_id,
        assessed_at=ASSESSED_AT,
    ) == assessment_input(business_id)
    assert (
        await assessments.get_at(
            business_id=business_id,
            assessed_at=ASSESSED_AT,
        )
        is health
    )
    assert await assessments.get_latest(business_id=business_id) is health
    assert (
        await traces.get_traceability(
            business_id=business_id,
            assessed_at=ASSESSED_AT,
        )
        is traceability
    )


async def test_read_provider_contracts_preserve_authoritative_boundaries() -> None:
    """Providers supply inputs and outputs without invoking assessment behavior."""
    business_id = uuid.uuid4()
    source_input = assessment_input(business_id)
    health = assessment(business_id)
    input_provider = FakeInputProvider(source_input)
    read_provider = FakeReadProvider(health)

    assert isinstance(input_provider, BusinessHealthInputProvider)
    assert isinstance(read_provider, BusinessHealthReadProvider)
    assert (
        await input_provider.provide_input(
            business_id=business_id,
            assessed_at=ASSESSED_AT,
        )
        is source_input
    )
    assert (
        await read_provider.get_current(
            business_id=business_id,
            assessed_at=ASSESSED_AT,
        )
        is health
    )
