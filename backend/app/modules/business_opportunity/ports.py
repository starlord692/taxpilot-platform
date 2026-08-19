"""Technology-agnostic, read-only boundaries for Business Opportunity v1.0."""

import uuid
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.modules.business_forecast.models import PublishedForecast
from app.modules.business_opportunity.models import BusinessOpportunity


@runtime_checkable
class BusinessOpportunityInputProvider(Protocol):
    async def get_published_forecast(
        self, *, business_id: uuid.UUID
    ) -> PublishedForecast | None: ...


@runtime_checkable
class BusinessOpportunityRepository(Protocol):
    async def get(self, *, opportunity_id: uuid.UUID) -> BusinessOpportunity | None: ...


@runtime_checkable
class BusinessOpportunityHistoryRepository(Protocol):
    async def get_history(
        self, *, business_id: uuid.UUID
    ) -> tuple[BusinessOpportunity, ...]: ...


@runtime_checkable
class BusinessOpportunityTraceabilityRepository(Protocol):
    async def get_traceability(
        self, *, opportunity_id: uuid.UUID
    ) -> BusinessOpportunity | None: ...


@runtime_checkable
class BusinessOpportunityReadProvider(Protocol):
    async def get_collection(
        self, *, business_id: uuid.UUID
    ) -> tuple[BusinessOpportunity, ...]:
        """Return the owner-published collection in its authoritative order."""
        ...

    async def get_at_time(
        self, *, business_id: uuid.UUID, assessment_time: datetime
    ) -> tuple[BusinessOpportunity, ...]: ...
