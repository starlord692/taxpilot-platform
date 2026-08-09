"""Focused contract tests for FORECAST-003 technology-agnostic boundaries."""

import inspect
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.business_forecast.models import (
    ForecastAssumption,
    ForecastExplanationReferences,
    ForecastHorizon,
    ForecastIdentity,
    ForecastLimitation,
    ForecastSourceReference,
    ForecastTraceability,
    PublishedForecast,
)
from app.modules.business_forecast.ports import (
    ForecastHistoryRepository,
    ForecastInputProvider,
    ForecastReadProvider,
    ForecastRepository,
    ForecastTraceabilityRepository,
)
from app.modules.business_forecast.service import (
    BusinessForecastInput,
    BusinessForecastService,
)


def _assessment_time() -> datetime:
    return datetime(2026, 8, 1, 9, tzinfo=UTC)


def _identity(*, business_id: uuid.UUID | None = None) -> ForecastIdentity:
    return ForecastIdentity(
        business_id=business_id or uuid.UUID("12345678-1234-5678-1234-567812345678"),
        assessed_at=_assessment_time(),
        horizon=ForecastHorizon(reference="90 days"),
        published_version="1",
    )


def _input(*, identity: ForecastIdentity | None = None) -> BusinessForecastInput:
    forecast_identity = identity or _identity()
    limitation = ForecastLimitation(
        reference="confidence-limitation-001",
        description="Current understanding has published coverage limitations.",
        source_reference="confidence-assessment-001",
    )
    source_references = tuple(
        ForecastSourceReference(
            capability=capability,
            published_identity=f"{capability.lower().replace(' ', '-')}-001",
            provenance_reference=f"{capability.lower().replace(' ', '-')}-source-001",
            assessed_at=forecast_identity.assessed_at,
        )
        for capability in (
            "Business DNA",
            "Business Health",
            "Business Momentum",
            "Business Confidence",
            "Business Brief",
        )
    )
    return BusinessForecastInput(
        identity=forecast_identity,
        projection="Authoritative deterministic future-state projection.",
        assumptions=(
            ForecastAssumption(
                reference="assumption-001",
                description="Published present-state conditions continue.",
                source_reference="forecast-policy-v1",
            ),
        ),
        limitations=(limitation,),
        traceability=ForecastTraceability(
            source_references=source_references,
            policy_version="forecast-policy-v1",
            explanation_references=ForecastExplanationReferences(
                references=("forecast-explanation-001",)
            ),
        ),
        created_at=forecast_identity.assessed_at + timedelta(minutes=1),
        published_at=forecast_identity.assessed_at + timedelta(minutes=2),
    )


class _FakeForecastInputProvider:
    """Test-only in-memory provider for canonical supplied assembly input."""

    def __init__(self, inputs: dict[ForecastIdentity, BusinessForecastInput]) -> None:
        self._inputs = inputs

    async def provide_input(
        self,
        *,
        identity: ForecastIdentity,
    ) -> BusinessForecastInput:
        return self._inputs[identity]


class _FakeForecastRepository:
    """Test-only in-memory read boundary for published Forecast artifacts."""

    def __init__(self, forecasts: dict[ForecastIdentity, PublishedForecast]) -> None:
        self._forecasts = forecasts

    async def get_published(
        self,
        *,
        identity: ForecastIdentity,
    ) -> PublishedForecast | None:
        return self._forecasts.get(identity)


class _FakeForecastHistoryRepository:
    """Test-only in-memory read boundary for immutable Forecast history."""

    def __init__(
        self,
        history: dict[uuid.UUID, tuple[PublishedForecast, ...]],
    ) -> None:
        self._history = history

    async def get_history(
        self,
        *,
        business_id: uuid.UUID,
    ) -> tuple[PublishedForecast, ...]:
        return self._history.get(business_id, ())


class _FakeForecastTraceabilityRepository:
    """Test-only in-memory read boundary for Forecast traceability."""

    def __init__(
        self,
        traceability: dict[ForecastIdentity, ForecastTraceability],
    ) -> None:
        self._traceability = traceability

    async def get_traceability(
        self,
        *,
        identity: ForecastIdentity,
    ) -> ForecastTraceability | None:
        return self._traceability.get(identity)


class _FakeForecastReadProvider:
    """Test-only consumer read boundary for canonical published Forecasts."""

    def __init__(self, forecasts: dict[ForecastIdentity, PublishedForecast]) -> None:
        self._forecasts = forecasts

    async def get_published_forecast(
        self,
        *,
        identity: ForecastIdentity,
    ) -> PublishedForecast | None:
        return self._forecasts.get(identity)


def test_all_five_contracts_exist_and_accept_simple_fake_implementations() -> None:
    """Every approved Protocol is importable and runtime-compatible."""
    forecast_input = _input()
    published = BusinessForecastService().assemble(forecast_input)
    identity = forecast_input.identity

    input_provider = _FakeForecastInputProvider({identity: forecast_input})
    forecast_repository = _FakeForecastRepository({identity: published})
    history_repository = _FakeForecastHistoryRepository(
        {identity.business_id: (published,)}
    )
    traceability_repository = _FakeForecastTraceabilityRepository(
        {identity: forecast_input.traceability}
    )
    read_provider = _FakeForecastReadProvider({identity: published})

    assert isinstance(input_provider, ForecastInputProvider)
    assert isinstance(forecast_repository, ForecastRepository)
    assert isinstance(history_repository, ForecastHistoryRepository)
    assert isinstance(traceability_repository, ForecastTraceabilityRepository)
    assert isinstance(read_provider, ForecastReadProvider)


@pytest.mark.asyncio
async def test_contracts_preserve_exact_identity_and_traceability() -> None:
    """Input, artifact, and traceability boundaries preserve canonical structures."""
    forecast_input = _input()
    published = BusinessForecastService().assemble(forecast_input)
    identity = forecast_input.identity

    input_provider = _FakeForecastInputProvider({identity: forecast_input})
    forecast_repository = _FakeForecastRepository({identity: published})
    traceability_repository = _FakeForecastTraceabilityRepository(
        {identity: forecast_input.traceability}
    )
    read_provider = _FakeForecastReadProvider({identity: published})

    assert await input_provider.provide_input(identity=identity) is forecast_input
    assert await forecast_repository.get_published(identity=identity) is published
    assert (
        await traceability_repository.get_traceability(identity=identity)
        is forecast_input.traceability
    )
    assert await read_provider.get_published_forecast(identity=identity) is published


@pytest.mark.asyncio
async def test_business_scoped_retrieval_does_not_cross_business_boundaries() -> None:
    """A different business identity cannot retrieve another business's artifact."""
    forecast_input = _input()
    published = BusinessForecastService().assemble(forecast_input)
    other_identity = _identity(
        business_id=uuid.UUID("87654321-4321-8765-4321-876543218765")
    )
    forecast_repository = _FakeForecastRepository(
        {forecast_input.identity: published}
    )
    read_provider = _FakeForecastReadProvider({forecast_input.identity: published})

    assert await forecast_repository.get_published(identity=other_identity) is None
    assert await read_provider.get_published_forecast(identity=other_identity) is None


@pytest.mark.asyncio
async def test_history_retrieval_preserves_the_original_immutable_artifact() -> None:
    """Historical retrieval returns the existing artifact rather than a replacement."""
    forecast_input = _input()
    published = BusinessForecastService().assemble(forecast_input)
    history_repository = _FakeForecastHistoryRepository(
        {forecast_input.identity.business_id: (published,)}
    )

    history = await history_repository.get_history(
        business_id=forecast_input.identity.business_id
    )

    assert history == (published,)
    assert history[0] is published
    assert history[0].forecast.traceability is forecast_input.traceability


def test_contract_module_uses_only_domain_structures_and_protocols() -> None:
    """The production contract layer has no framework or storage dependency."""
    source = inspect.getsource(
        __import__("app.modules.business_forecast.ports", fromlist=["ports"])
    ).lower()

    for forbidden_name in (
        "sqlalchemy",
        "fastapi",
        "redis",
        "http",
        "session",
        "adapter",
        "cache",
    ):
        assert forbidden_name not in source
