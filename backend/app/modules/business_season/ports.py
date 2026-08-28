"""Technology-neutral, read-only owner-controlled Business Season contracts."""

import uuid
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.modules.business_season.models import (
    BusinessSeason,
    SeasonAuthoritativeInput,
    SemanticInputReference,
)


@runtime_checkable
class BusinessSeasonInputProvider(Protocol):
    async def get_inputs(
        self, *, business_id: uuid.UUID, semantic_input: SemanticInputReference
    ) -> tuple[SeasonAuthoritativeInput, ...]: ...


@runtime_checkable
class BusinessSeasonReadProvider(Protocol):
    async def get_at_time(
        self, *, business_id: uuid.UUID, assessment_time: datetime
    ) -> tuple[BusinessSeason, ...]: ...

    async def get_history(
        self, *, business_id: uuid.UUID
    ) -> tuple[BusinessSeason, ...]: ...
