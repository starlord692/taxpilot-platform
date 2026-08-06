"""Unit tests for FORECAST-001 immutable Business Forecast domain models."""

import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.business_forecast.models import (
    BusinessForecast,
    ForecastAssumption,
    ForecastExplanationReferences,
    ForecastHorizon,
    ForecastIdentity,
    ForecastLimitation,
    ForecastSourceReference,
    ForecastTraceability,
    HistoricalForecastIdentity,
    PublishedForecast,
)


def _assessment_time() -> datetime:
    return datetime(2026, 8, 1, 9, tzinfo=UTC)


def _limitation() -> ForecastLimitation:
    return ForecastLimitation(
        reference="confidence-limitation-001",
        description="Current understanding has published coverage limitations.",
        source_reference="confidence-assessment-001",
    )


def _forecast() -> BusinessForecast:
    assessed_at = _assessment_time()
    source = ForecastSourceReference(
        capability="Business Confidence",
        published_identity="confidence-assessment-001",
        provenance_reference="confidence-evidence-001",
        assessed_at=assessed_at,
        limitations=(_limitation(),),
    )
    traceability = ForecastTraceability(
        source_references=(source,),
        policy_version="forecast-policy-v1",
        explanation_references=ForecastExplanationReferences(
            references=("forecast-explanation-001",)
        ),
    )
    return BusinessForecast(
        identity=ForecastIdentity(
            business_id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
            assessed_at=assessed_at,
            horizon=ForecastHorizon(reference="90 days"),
            published_version="1",
        ),
        projection="Authoritative deterministic future-state projection.",
        assumptions=(
            ForecastAssumption(
                reference="assumption-001",
                description="Published present-state conditions continue.",
                source_reference="forecast-policy-v1",
            ),
        ),
        limitations=(_limitation(),),
        traceability=traceability,
        created_at=assessed_at + timedelta(minutes=1),
    )


def test_business_forecast_preserves_the_complete_authoritative_structure() -> None:
    """A model preserves supplied identity, projection, and traceability unchanged."""
    forecast = _forecast()

    assert forecast.identity.horizon.reference == "90 days"
    assert forecast.projection == "Authoritative deterministic future-state projection."
    assert forecast.assumptions[0].reference == "assumption-001"
    assert forecast.limitations[0].reference == "confidence-limitation-001"
    assert (
        forecast.traceability.source_references[0].capability
        == "Business Confidence"
    )
    assert forecast.traceability.explanation_references.references == (
        "forecast-explanation-001",
    )


def test_business_forecast_models_are_immutable() -> None:
    """Published model structures cannot be changed after creation."""
    forecast = _forecast()

    with pytest.raises(FrozenInstanceError):
        forecast.projection = "Replacement projection"  # type: ignore[misc]


def test_forecast_horizon_requires_an_explicit_reference() -> None:
    """A forecast cannot have an unspecified horizon."""
    with pytest.raises(ValueError, match="forecast horizon reference"):
        ForecastHorizon(reference=" ")


def test_forecast_assumption_requires_traceability() -> None:
    """Forecast assumptions cannot be hidden or anonymous."""
    with pytest.raises(ValueError, match="source reference"):
        ForecastAssumption(
            reference="assumption-001",
            description="Published condition.",
            source_reference=" ",
        )


def test_traceability_requires_sources_and_explanation_references() -> None:
    """A Forecast does not permit incomplete deterministic traceability."""
    with pytest.raises(ValueError, match="source references"):
        ForecastTraceability(
            source_references=(),
            policy_version="forecast-policy-v1",
            explanation_references=ForecastExplanationReferences(
                references=("forecast-explanation-001",)
            ),
        )

    with pytest.raises(ValueError, match="explanation references"):
        ForecastExplanationReferences(references=())


def test_business_forecast_requires_explicit_assumptions() -> None:
    """The model does not permit implicit forecast assumptions."""
    forecast = _forecast()

    with pytest.raises(ValueError, match="explicit assumptions"):
        BusinessForecast(
            identity=forecast.identity,
            projection=forecast.projection,
            assumptions=(),
            limitations=forecast.limitations,
            traceability=forecast.traceability,
            created_at=forecast.created_at,
        )


def test_business_forecast_rejects_future_source_context() -> None:
    """A Forecast cannot trace itself to knowledge assessed after itself."""
    forecast = _forecast()
    future_source = ForecastSourceReference(
        capability="Business Health",
        published_identity="health-assessment-002",
        provenance_reference="health-evidence-002",
        assessed_at=forecast.identity.assessed_at + timedelta(seconds=1),
    )
    future_traceability = ForecastTraceability(
        source_references=(future_source,),
        policy_version="forecast-policy-v1",
        explanation_references=forecast.traceability.explanation_references,
    )

    with pytest.raises(ValueError, match="cannot be assessed after"):
        BusinessForecast(
            identity=forecast.identity,
            projection=forecast.projection,
            assumptions=forecast.assumptions,
            limitations=forecast.limitations,
            traceability=future_traceability,
            created_at=forecast.created_at,
        )


def test_business_forecast_rejects_creation_before_assessment() -> None:
    """A point-in-time Forecast cannot be created before it is assessed."""
    forecast = _forecast()

    with pytest.raises(ValueError, match="cannot precede forecast assessment"):
        BusinessForecast(
            identity=forecast.identity,
            projection=forecast.projection,
            assumptions=forecast.assumptions,
            limitations=forecast.limitations,
            traceability=forecast.traceability,
            created_at=forecast.identity.assessed_at - timedelta(seconds=1),
        )


def test_published_and_historical_forecasts_preserve_chronology() -> None:
    """Publication and historical identity cannot precede their Forecast assessment."""
    forecast = _forecast()
    published = PublishedForecast(
        forecast=forecast,
        published_at=forecast.created_at + timedelta(minutes=1),
    )
    historical_identity = HistoricalForecastIdentity(
        identity=forecast.identity,
        published_at=published.published_at,
    )

    assert published.forecast is forecast
    assert historical_identity.identity == forecast.identity

    with pytest.raises(
        ValueError,
        match="publication cannot precede forecast creation",
    ):
        PublishedForecast(
            forecast=forecast,
            published_at=forecast.created_at - timedelta(seconds=1),
        )


def test_duplicate_traceability_and_references_are_rejected() -> None:
    """Duplicate deterministic references cannot obscure the source chain."""
    forecast = _forecast()
    source = forecast.traceability.source_references[0]

    with pytest.raises(ValueError, match="must not be duplicated"):
        ForecastTraceability(
            source_references=(source, source),
            policy_version="forecast-policy-v1",
            explanation_references=forecast.traceability.explanation_references,
        )

    with pytest.raises(ValueError, match="must not be duplicated"):
        ForecastExplanationReferences(
            references=("forecast-explanation-001", "forecast-explanation-001")
        )
