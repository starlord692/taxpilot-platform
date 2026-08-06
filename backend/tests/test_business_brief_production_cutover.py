"""ES-007 Phase 4 production-route tests for the ES-001 experience boundary."""

import uuid

import pytest

from app.modules.business_brief.models import BusinessBriefRequest
from app.modules.business_brief.service import BusinessBriefService
from tests.test_business_brief_compatibility_facade import (
    canonical_input,
    facade,
)
from tests.test_business_brief_service import AS_OF, make_service

pytestmark = pytest.mark.asyncio


async def test_es001_public_service_routes_through_compatibility_facade() -> None:
    """The public ES-001 boundary delegates request handling to ES-007."""
    business_id = uuid.uuid4()
    supplied = canonical_input(business_id)
    compatibility_facade, _, _, _ = facade(value=supplied)
    service = BusinessBriefService(compatibility_facade=compatibility_facade)

    result = await service.get_brief(
        BusinessBriefRequest(
            business_id=business_id,
            user_id=uuid.uuid4(),
            as_of=AS_OF,
        )
    )

    assert result.projection_status == "available"
    assert result.canonical_brief is not None
    assert result.canonical_brief.narrative_items is supplied.narrative_items
    assert result.canonical_explanation is not None
    assert result.canonical_explanation.brief is result.canonical_brief


async def test_legacy_assembler_remains_available_only_for_rollback_validation() -> (
    None
):
    """The original characterized route remains separate from production routing."""
    business_id = uuid.uuid4()
    rollback_service = make_service(business_id=business_id)

    result = await rollback_service.get_brief(
        BusinessBriefRequest(
            business_id=business_id,
            user_id=uuid.uuid4(),
            as_of=AS_OF,
        )
    )

    assert result.canonical_brief is None
    assert result.projection_status is None
