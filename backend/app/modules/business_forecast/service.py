"""Deterministic assembly service for the Business Forecast capability.

The service assembles a supplied immutable Forecast from authoritative
published structures. It does not calculate a projection, implement policy,
infer outcomes, call AI, retrieve or persist data, or expose an API.
"""

from dataclasses import dataclass
from datetime import datetime

from app.modules.business_forecast.models import (
    BusinessForecast,
    ForecastAssumption,
    ForecastIdentity,
    ForecastLimitation,
    ForecastTraceability,
    PublishedForecast,
)

_MANDATORY_SOURCE_CAPABILITIES = frozenset(
    {
        "Business DNA",
        "Business Health",
        "Business Momentum",
        "Business Confidence",
        "Business Brief",
    }
)

_AUTHORIZED_SOURCE_CAPABILITIES = _MANDATORY_SOURCE_CAPABILITIES | frozenset(
    {
        "Business Goals",
        "Business Season",
        "Founder-approved Business Context",
        "Founder-approved Deterministic Business Activity",
    }
)


@dataclass(frozen=True, slots=True)
class BusinessForecastInput:
    """Authoritative supplied structures used to assemble a published Forecast.

    ``projection`` and ``traceability`` are supplied by the approved caller and
    are preserved exactly. This input does not provide a mechanism for Forecast
    calculation, policy evaluation, or source-capability redefinition.
    """

    identity: ForecastIdentity
    projection: str
    assumptions: tuple[ForecastAssumption, ...]
    limitations: tuple[ForecastLimitation, ...]
    traceability: ForecastTraceability
    created_at: datetime
    published_at: datetime


class BusinessForecastService:
    """Assemble a published Forecast from authoritative supplied structures only."""

    def assemble(self, forecast_input: BusinessForecastInput) -> PublishedForecast:
        """Return an immutable published Forecast without determining its projection."""
        self._validate_authoritative_sources(forecast_input)
        forecast = BusinessForecast(
            identity=forecast_input.identity,
            projection=forecast_input.projection,
            assumptions=forecast_input.assumptions,
            limitations=forecast_input.limitations,
            traceability=forecast_input.traceability,
            created_at=forecast_input.created_at,
        )
        return PublishedForecast(
            forecast=forecast,
            published_at=forecast_input.published_at,
        )

    @staticmethod
    def _validate_authoritative_sources(
        forecast_input: BusinessForecastInput,
    ) -> None:
        """Require KP-006 mandatory sources and reject unapproved source owners."""
        source_capabilities = frozenset(
            source.capability
            for source in forecast_input.traceability.source_references
        )
        missing_capabilities = _MANDATORY_SOURCE_CAPABILITIES - source_capabilities
        if missing_capabilities:
            missing = ", ".join(sorted(missing_capabilities))
            raise ValueError(
                "business forecast requires mandatory authoritative sources: "
                f"{missing}"
            )
        unsupported_capabilities = (
            source_capabilities - _AUTHORIZED_SOURCE_CAPABILITIES
        )
        if unsupported_capabilities:
            unsupported = ", ".join(sorted(unsupported_capabilities))
            raise ValueError(
                "business forecast cannot consume unapproved source capabilities: "
                f"{unsupported}"
            )
