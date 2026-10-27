"""Business Understanding API router."""

import uuid
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.responses import ErrorResponse, SuccessResponse
from app.modules.business_understanding.api.dependencies import (
    get_business_understanding_service,
)
from app.modules.business_understanding.schemas import BusinessUnderstandingResponse
from app.modules.business_understanding.services import BusinessUnderstandingService
from app.modules.identity.dependencies import CurrentUser

router = APIRouter(prefix="/business-understanding", tags=["Business Understanding"])
ServiceDependency = Annotated[
    BusinessUnderstandingService,
    Depends(get_business_understanding_service),
]


@router.get(
    "",
    response_model=SuccessResponse[BusinessUnderstandingResponse],
    status_code=status.HTTP_200_OK,
    summary="Read current business understanding",
    description=(
        "Returns a deterministic, read-only snapshot of existing Accounting "
        "facts for an authorized business member."
    ),
    responses={
        HTTPStatus.OK: {"description": "Business facts returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
    },
)
async def get_business_understanding(
    current_user: CurrentUser,
    service: ServiceDependency,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID scope.")],
) -> SuccessResponse[BusinessUnderstandingResponse]:
    """Return current Accounting facts for one authorized business."""
    snapshot = await service.get_snapshot(business_id, current_user.id)
    return SuccessResponse(
        success=True,
        message="Business understanding returned successfully",
        data=snapshot,
    )
