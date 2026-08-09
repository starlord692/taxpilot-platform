"""Technology-agnostic read-only contracts for Business Forecast.

These Protocols define dependency boundaries only. They preserve canonical
Forecast identity, temporal context, traceability, historical artifacts, and
business isolation without prescribing how any dependency is implemented.
"""

import uuid
from typing import Protocol, runtime_checkable

from app.modules.business_forecast.models import (
    ForecastIdentity,
    ForecastTraceability,
    PublishedForecast,
)
from app.modules.business_forecast.service import BusinessForecastInput


@runtime_checkable
class ForecastInputProvider(Protocol):
    """Provide authoritative published input for one exact Forecast identity."""

    async def provide_input(
        self,
        *,
        identity: ForecastIdentity,
    ) -> BusinessForecastInput:
        """Return supplied canonical input without recalculation or reinterpretation."""
        ...


@runtime_checkable
class ForecastRepository(Protocol):
    """Read an already-published Forecast without prescribing its storage."""

    async def get_published(
        self,
        *,
        identity: ForecastIdentity,
    ) -> PublishedForecast | None:
        """Return the exact published artifact when it is available."""
        ...


@runtime_checkable
class ForecastHistoryRepository(Protocol):
    """Read immutable historical Forecast artifacts for one business."""

    async def get_history(
        self,
        *,
        business_id: uuid.UUID,
    ) -> tuple[PublishedForecast, ...]:
        """Return preserved historical artifacts without mutation semantics."""
        ...


@runtime_checkable
class ForecastTraceabilityRepository(Protocol):
    """Read the complete deterministic traceability for one Forecast identity."""

    async def get_traceability(
        self,
        *,
        identity: ForecastIdentity,
    ) -> ForecastTraceability | None:
        """Return canonical source, policy, and explanation traceability."""
        ...


@runtime_checkable
class ForecastReadProvider(Protocol):
    """Provide an already-published canonical Forecast to approved consumers."""

    async def get_published_forecast(
        self,
        *,
        identity: ForecastIdentity,
    ) -> PublishedForecast | None:
        """Return the immutable artifact without reconstruction or replacement."""
        ...


__all__ = [
    "ForecastHistoryRepository",
    "ForecastInputProvider",
    "ForecastReadProvider",
    "ForecastRepository",
    "ForecastTraceabilityRepository",
]
