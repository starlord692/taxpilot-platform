"""Read-only HTTP transport for owner-published Business Opportunities."""

import uuid
from http import HTTPStatus
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query

from app.common.exceptions import InfrastructureException
from app.common.unit_of_work import SQLAlchemyUnitOfWork
from app.core.responses import ErrorResponse, SuccessResponse
from app.modules.business.api.context import (
    BusinessContextUnitOfWork,
    ensure_active_business_membership,
)
from app.modules.business.api.dependencies import get_session_factory
from app.modules.business_opportunity.api.dependencies import (
    get_business_opportunity_read_provider,
)
from app.modules.business_opportunity.api.schemas import BusinessOpportunityResponse
from app.modules.business_opportunity.ports import BusinessOpportunityReadProvider
from app.modules.identity.dependencies import CurrentUser

router = APIRouter(prefix="/opportunities", tags=["Opportunities"])
ReadProvider = Annotated[
    BusinessOpportunityReadProvider,
    Depends(get_business_opportunity_read_provider),
]


@router.get(
    "",
    response_model=SuccessResponse[tuple[BusinessOpportunityResponse, ...]],
    responses={
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
    },
    summary="Read authoritative Business Opportunities",
)
async def get_opportunities(
    current_user: CurrentUser,
    provider: ReadProvider,
    business_id: Annotated[uuid.UUID, Query()],
) -> SuccessResponse[tuple[BusinessOpportunityResponse, ...]]:
    """Return the provider-published collection after business-context validation."""
    async with SQLAlchemyUnitOfWork(get_session_factory()) as uow:
        await ensure_active_business_membership(
            cast(BusinessContextUnitOfWork, uow),
            business_id=business_id,
            user_id=current_user.id,
            entered=True,
        )
    opportunities = await provider.get_collection(business_id=business_id)
    if any(item.business_id != business_id for item in opportunities):
        raise InfrastructureException(
            "Business Opportunity provider returned a foreign business"
        )
    return SuccessResponse(
        success=True,
        message="Business Opportunities returned successfully",
        data=tuple(
            BusinessOpportunityResponse.from_opportunity(item) for item in opportunities
        ),
    )
