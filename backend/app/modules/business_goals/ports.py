"""Technology-neutral, read-only contracts for Business Goals v1.0."""

import uuid
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.modules.business_goals.models import BusinessGoal


@runtime_checkable
class BusinessGoalReadProvider(Protocol):
    """Owner-controlled read boundary for authorized Business Goal retrieval."""

    async def get_current(
        self, *, business_id: uuid.UUID, context_time: datetime
    ) -> tuple[BusinessGoal, ...]:
        """Return all applicable Published Goals in deterministic non-ranking order."""
        ...

    async def get_history(
        self, *, business_id: uuid.UUID
    ) -> tuple[BusinessGoal, ...]:
        """Return immutable Published Goal history for one authorized business."""
        ...
