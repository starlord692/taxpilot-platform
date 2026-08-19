"""Focused tests for the Business Opportunity read transport."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

import pytest

from app.common.exceptions import InfrastructureException
from app.modules.business_forecast.models import ForecastAuthoritativeInput
from app.modules.business_opportunity.api.router import get_opportunities
from app.modules.business_opportunity.models import (
    BusinessOpportunity,
    OpportunityStatus,
)
from app.modules.business_opportunity.ports import BusinessOpportunityReadProvider
from app.modules.identity.models import IdentityUser


def _opportunity(
    business_id: uuid.UUID,
    subject: str,
) -> BusinessOpportunity:
    assessment_time = datetime(2026, 8, 17, tzinfo=UTC)
    source = ForecastAuthoritativeInput(
        "PublishedForecast",
        "Business Health",
        "health-input-1",
        "state",
        "enum",
        "good",
    )
    return BusinessOpportunity(
        opportunity_id=uuid.uuid4(),
        business_id=business_id,
        status=OpportunityStatus.ELIGIBLE,
        assessment_time=assessment_time,
        opportunity_type="growth",
        canonical_subject=subject,
        policy_id="opportunity-policy-1",
        policy_version="1.0",
        eligibility_result=OpportunityStatus.ELIGIBLE,
        source_references=(source,),
        evidence=(source,),
        limitations=("authoritative limitation",),
        input_traceability=(source,),
        provenance="founder-approved",
        temporal_context=assessment_time,
        condition_evaluations=(),
        unavailable_information=(),
    )


class _OrderedProvider:
    def __init__(self, opportunities: tuple[BusinessOpportunity, ...]) -> None:
        self._opportunities = opportunities
        self.business_ids: list[uuid.UUID] = []

    async def get_collection(
        self, *, business_id: uuid.UUID
    ) -> tuple[BusinessOpportunity, ...]:
        self.business_ids.append(business_id)
        return self._opportunities

    async def get_at_time(
        self, *, business_id: uuid.UUID, assessment_time: datetime
    ) -> tuple[BusinessOpportunity, ...]:
        return self._opportunities


class _UnitOfWork:
    async def __aenter__(self) -> "_UnitOfWork":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


@pytest.mark.asyncio
async def test_collection_transport_preserves_provider_order_and_authority() -> None:
    business_id = uuid.uuid4()
    first = _opportunity(business_id, "first")
    second = _opportunity(business_id, "second")
    provider = _OrderedProvider((second, first))
    validated: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def validate(
        _uow: object, *, business_id: uuid.UUID, user_id: uuid.UUID, entered: bool
    ) -> None:
        assert entered is True
        validated.append((business_id, user_id))

    with (
        patch(
            "app.modules.business_opportunity.api.router.SQLAlchemyUnitOfWork",
            return_value=_UnitOfWork(),
        ),
        patch(
            "app.modules.business_opportunity.api.router.get_session_factory",
            return_value=object(),
        ),
        patch(
            "app.modules.business_opportunity.api.router.ensure_active_business_membership",
            new=validate,
        ),
    ):
        response = await get_opportunities(
            cast(IdentityUser, SimpleNamespace(id=uuid.uuid4())), provider, business_id
        )

    assert isinstance(provider, BusinessOpportunityReadProvider)
    assert provider.business_ids == [business_id]
    assert validated[0][0] == business_id
    assert tuple(item.canonical_subject for item in response.data or ()) == (
        "second",
        "first",
    )
    assert response.data is not None
    assert response.data[0].evidence[0].reference_id == "health-input-1"


@pytest.mark.asyncio
async def test_collection_transport_rejects_foreign_business_artifacts() -> None:
    requested_business_id = uuid.uuid4()
    provider = _OrderedProvider((_opportunity(uuid.uuid4(), "foreign"),))

    async def validate(*args: object, **kwargs: object) -> None:
        return None

    with (
        patch(
            "app.modules.business_opportunity.api.router.SQLAlchemyUnitOfWork",
            return_value=_UnitOfWork(),
        ),
        patch(
            "app.modules.business_opportunity.api.router.get_session_factory",
            return_value=object(),
        ),
        patch(
            "app.modules.business_opportunity.api.router.ensure_active_business_membership",
            new=validate,
        ),
        pytest.raises(InfrastructureException, match="foreign business"),
    ):
        await get_opportunities(
            cast(IdentityUser, SimpleNamespace(id=uuid.uuid4())),
            provider,
            requested_business_id,
        )
