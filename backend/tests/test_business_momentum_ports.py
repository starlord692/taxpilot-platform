"""Contract tests for MOM-003 Business Momentum repository and provider ports."""

from dataclasses import replace
from datetime import timedelta

import pytest

from app.modules.business_momentum import (
    BusinessMomentumAssessment,
    BusinessMomentumAssessmentInput,
    BusinessMomentumAssessmentRepository,
    BusinessMomentumHistoryRepository,
    BusinessMomentumInputProvider,
    BusinessMomentumReadProvider,
    BusinessMomentumSourceRepository,
    BusinessMomentumTraceability,
    BusinessMomentumTraceabilityRepository,
)
from tests.test_business_momentum_models import assessment
from tests.test_business_momentum_service import assessment_input

pytestmark = pytest.mark.asyncio


class FakeSourceRepository:
    """In-memory source repository contract fake."""

    def __init__(self, value: BusinessMomentumAssessmentInput) -> None:
        self.value = value

    async def get_assessment_input(
        self,
        *,
        business_id: object,
        assessed_at: object,
    ) -> BusinessMomentumAssessmentInput:
        """Return configured authoritative input."""
        assert business_id == self.value.business_id
        assert assessed_at == self.value.assessed_at
        return self.value


class FakeAssessmentRepository:
    """In-memory assessment repository contract fake."""

    def __init__(self, value: BusinessMomentumAssessment) -> None:
        self.value = value

    async def get_at(
        self,
        *,
        business_id: object,
        assessed_at: object,
    ) -> BusinessMomentumAssessment | None:
        """Return configured assessment for a matching request."""
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
    ) -> BusinessMomentumAssessment | None:
        """Return configured latest assessment for a matching business."""
        return self.value if business_id == self.value.business_id else None


class FakeHistoryRepository:
    """In-memory assessment-history repository contract fake."""

    def __init__(self, values: tuple[BusinessMomentumAssessment, ...]) -> None:
        self.values = values

    async def get_assessment_history(
        self,
        *,
        business_id: object,
    ) -> tuple[BusinessMomentumAssessment, ...]:
        """Return configured history for one business only."""
        return tuple(value for value in self.values if value.business_id == business_id)


class FakeTraceabilityRepository:
    """In-memory deterministic-traceability repository contract fake."""

    def __init__(self, value: BusinessMomentumTraceability) -> None:
        self.value = value

    async def get_traceability(
        self,
        *,
        business_id: object,
        assessed_at: object,
    ) -> BusinessMomentumTraceability | None:
        """Return configured traceability for a matching assessment."""
        if (
            business_id == self.value.business_id
            and assessed_at == self.value.assessed_at
        ):
            return self.value
        return None


class FakeInputProvider:
    """In-memory authoritative-input provider contract fake."""

    def __init__(self, value: BusinessMomentumAssessmentInput) -> None:
        self.value = value

    async def provide_input(
        self,
        *,
        business_id: object,
        assessed_at: object,
    ) -> BusinessMomentumAssessmentInput:
        """Return configured input without calculating Momentum."""
        assert business_id == self.value.business_id
        assert assessed_at == self.value.assessed_at
        return self.value


class FakeReadProvider:
    """In-memory approved-consumer read-provider contract fake."""

    def __init__(self, value: BusinessMomentumAssessment) -> None:
        self.value = value

    async def get_current(
        self,
        *,
        business_id: object,
        assessed_at: object,
    ) -> BusinessMomentumAssessment | None:
        """Return configured authoritative output for a matching request."""
        if (
            business_id == self.value.business_id
            and assessed_at == self.value.assessed_at
        ):
            return self.value
        return None


def traceability(value: BusinessMomentumAssessment) -> BusinessMomentumTraceability:
    """Build traceability directly from authoritative Momentum output."""
    return BusinessMomentumTraceability(
        business_id=value.business_id,
        assessed_at=value.assessed_at,
        evidence=value.evidence,
        observed_changes=value.observed_changes,
        applied_policy_reference=value.applied_policy_reference,
        limitations=value.limitations,
    )


async def test_repository_contracts_are_read_only_and_technology_agnostic() -> None:
    """Repository ports are fulfilled without adapters, storage, or frameworks."""
    supplied = assessment_input()
    current = assessment()
    current = replace(
        current, business_id=supplied.business_id, assessed_at=supplied.assessed_at
    )
    earlier = replace(current, assessed_at=current.assessed_at - timedelta(days=1))
    source = FakeSourceRepository(supplied)
    assessments = FakeAssessmentRepository(current)
    history = FakeHistoryRepository((earlier, current))
    traces = FakeTraceabilityRepository(traceability(current))

    assert isinstance(source, BusinessMomentumSourceRepository)
    assert isinstance(assessments, BusinessMomentumAssessmentRepository)
    assert isinstance(history, BusinessMomentumHistoryRepository)
    assert isinstance(traces, BusinessMomentumTraceabilityRepository)
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
    assert await history.get_assessment_history(business_id=current.business_id) == (
        earlier,
        current,
    )
    assert await traces.get_traceability(
        business_id=current.business_id,
        assessed_at=current.assessed_at,
    ) == traceability(current)


async def test_provider_contracts_preserve_authoritative_consumer_boundaries() -> None:
    """Providers expose only supplied authoritative input and output."""
    supplied = assessment_input()
    current = assessment()
    current = replace(
        current, business_id=supplied.business_id, assessed_at=supplied.assessed_at
    )
    input_provider = FakeInputProvider(supplied)
    read_provider = FakeReadProvider(current)

    assert isinstance(input_provider, BusinessMomentumInputProvider)
    assert isinstance(read_provider, BusinessMomentumReadProvider)
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
