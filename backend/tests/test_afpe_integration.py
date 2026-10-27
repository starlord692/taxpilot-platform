"""Optional PostgreSQL integration checks for the AFPE persistence boundary."""

from __future__ import annotations

import os
from datetime import date
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_observation_period_read_fails_closed_without_configured_row() -> None:
    """A migrated AFPE database does not invent an observation period."""

    database_url = os.getenv("AFPE_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("AFPE_TEST_DATABASE_URL is not configured")
    pytest.importorskip("sqlalchemy")
    from sqlalchemy.ext.asyncio import (  # noqa: PLC0415
        AsyncSession,
        create_async_engine,
    )

    from app.modules.accounting.financial_performance_evidence.models import (  # noqa: PLC0415
        EvidencePerspective,
        ObservationContextRequest,
    )
    from app.modules.accounting.financial_performance_evidence.repository import (  # noqa: PLC0415
        SQLAlchemyObservationPeriodAdapter,
    )

    engine = create_async_engine(database_url)
    try:
        async with AsyncSession(engine) as session:
            adapter = SQLAlchemyObservationPeriodAdapter(
                session,
                supported_granularities=frozenset({"MONTHLY"}),
            )
            result = await adapter.resolve(
                business_id=uuid4(),
                request=ObservationContextRequest(
                    granularity="MONTHLY",
                    period_type="CALENDAR",
                    period_start=date(2099, 1, 1),
                    period_end=date(2099, 2, 1),
                ),
                perspective=EvidencePerspective.CURRENT_RECONSTRUCTION,
            )
            assert result is None
    finally:
        await engine.dispose()
