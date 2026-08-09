"""Unit tests for FORECAST-002 deterministic Forecast assembly."""

import uuid
from dataclasses import FrozenInstanceError
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
)
from app.modules.business_forecast.service import (
    BusinessForecastInput,
    BusinessForecastService,
)


def _assessment_time() -> datetime:
    return datetime(2026, 8, 1, 9, tzinfo=UTC)


def _limitation() -> ForecastLimitation:
    return ForecastLimitation(
        reference="confidence-limitation-001",
        description="Current understanding has published coverage limitations.",
        source_reference="confidence-assessment-001",
    )


def _source(capability: str) -> ForecastSourceReference:
    return ForecastSourceReference(
        capability=capability,
        published_identity=f"{capability.lower().replace(' ', '-')}-001",
        provenance_reference=f"{capability.lower().replace(' ', '-')}-evidence-001",
        assessed_at=_assessment_time(),
    )


def _forecast_input() -> BusinessForecastInput:
    assessed_at = _assessment_time()
    sources = tuple(
        _source(capability)
        for capability in (
            "Business DNA",
            "Business Health",
            "Business Momentum",
            "Business Confidence",
            "Business Brief",
        )
    )
    return BusinessForecastInput(
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
        traceability=ForecastTraceability(
            source_references=sources,
            policy_version="forecast-policy-v1",
            explanation_references=ForecastExplanationReferences(
                references=("forecast-explanation-001",)
            ),
        ),
        created_at=assessed_at + timedelta(minutes=1),
        published_at=assessed_at + timedelta(minutes=2),
    )


def test_assemble_preserves_authoritative_structures_exactly() -> None:
    """Assembly preserves supplied Forecast identity and content without alteration."""
    forecast_input = _forecast_input()
    published = BusinessForecastService().assemble(forecast_input)

    assert published.forecast.identity is forecast_input.identity
    assert published.forecast.projection == forecast_input.projection
    assert published.forecast.assumptions is forecast_input.assumptions
    assert published.forecast.limitations is forecast_input.limitations
    assert published.forecast.traceability is forecast_input.traceability
    assert published.published_at == forecast_input.published_at


def test_assemble_is_deterministic_for_identical_authoritative_input() -> None:
    """The same supplied structures always create equal published Forecasts."""
    forecast_input = _forecast_input()
    service = BusinessForecastService()

    assert service.assemble(forecast_input) == service.assemble(forecast_input)


def test_assemble_returns_an_immutable_published_forecast() -> None:
    """Assembly returns the immutable publication artifact defined by FORECAST-001."""
    published = BusinessForecastService().assemble(_forecast_input())

    with pytest.raises(FrozenInstanceError):
        published.published_at = _assessment_time()  # type: ignore[misc]


def test_assemble_rejects_missing_mandatory_authoritative_source() -> None:
    """KP-006 mandatory present-state capabilities cannot be silently omitted."""
    forecast_input = _forecast_input()
    missing_brief = tuple(
        source
        for source in forecast_input.traceability.source_references
        if source.capability != "Business Brief"
    )
    incomplete_input = BusinessForecastInput(
        identity=forecast_input.identity,
        projection=forecast_input.projection,
        assumptions=forecast_input.assumptions,
        limitations=forecast_input.limitations,
        traceability=ForecastTraceability(
            source_references=missing_brief,
            policy_version=forecast_input.traceability.policy_version,
            explanation_references=forecast_input.traceability.explanation_references,
        ),
        created_at=forecast_input.created_at,
        published_at=forecast_input.published_at,
    )

    with pytest.raises(ValueError, match="Business Brief"):
        BusinessForecastService().assemble(incomplete_input)


def test_assemble_rejects_an_unapproved_source_capability() -> None:
    """The assembly boundary does not consume downstream or speculative sources."""
    forecast_input = _forecast_input()
    traceability = ForecastTraceability(
        source_references=(
            *forecast_input.traceability.source_references,
            _source("Business Risk"),
        ),
        policy_version=forecast_input.traceability.policy_version,
        explanation_references=forecast_input.traceability.explanation_references,
    )
    unsupported_input = BusinessForecastInput(
        identity=forecast_input.identity,
        projection=forecast_input.projection,
        assumptions=forecast_input.assumptions,
        limitations=forecast_input.limitations,
        traceability=traceability,
        created_at=forecast_input.created_at,
        published_at=forecast_input.published_at,
    )

    with pytest.raises(ValueError, match="Business Risk"):
        BusinessForecastService().assemble(unsupported_input)


def test_assemble_delegates_future_source_validation_to_domain_models() -> None:
    """Sources assessed after the Forecast assessment remain invalid at assembly."""
    forecast_input = _forecast_input()
    sources = (
        ForecastSourceReference(
            capability="Business DNA",
            published_identity="business-dna-001",
            provenance_reference="business-dna-evidence-001",
            assessed_at=_assessment_time() + timedelta(seconds=1),
        ),
        *forecast_input.traceability.source_references[1:],
    )
    temporal_input = BusinessForecastInput(
        identity=forecast_input.identity,
        projection=forecast_input.projection,
        assumptions=forecast_input.assumptions,
        limitations=forecast_input.limitations,
        traceability=ForecastTraceability(
            source_references=sources,
            policy_version=forecast_input.traceability.policy_version,
            explanation_references=forecast_input.traceability.explanation_references,
        ),
        created_at=forecast_input.created_at,
        published_at=forecast_input.published_at,
    )

    with pytest.raises(ValueError, match="cannot be assessed after"):
        BusinessForecastService().assemble(temporal_input)


def test_assemble_delegates_publication_integrity_to_domain_models() -> None:
    """Publication chronology remains enforced by the FORECAST-001 artifact."""
    forecast_input = _forecast_input()
    premature_publication_input = BusinessForecastInput(
        identity=forecast_input.identity,
        projection=forecast_input.projection,
        assumptions=forecast_input.assumptions,
        limitations=forecast_input.limitations,
        traceability=forecast_input.traceability,
        created_at=forecast_input.created_at,
        published_at=forecast_input.created_at - timedelta(seconds=1),
    )

    with pytest.raises(ValueError, match="publication cannot precede"):
        BusinessForecastService().assemble(premature_publication_input)
