"""Financial Performance Business Momentum API router."""

from __future__ import annotations

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.responses import ErrorResponse, SuccessResponse
from app.modules.accounting.financial_performance_evidence.models import (
    AuthorizationContext,
    ObservationContextRequest,
)
from app.modules.identity.dependencies import CurrentUser
from app.modules.momentum.api.dependencies import get_momentum_service
from app.modules.momentum.schemas import (
    EvaluateFinancialPerformanceRequest,
    FinancialPerformanceDimensionResponse,
)
from app.modules.momentum.service import FinancialPerformanceMomentumService

router = APIRouter(prefix="/momentum", tags=["Business Momentum"])
MomentumServiceDependency = Annotated[
    FinancialPerformanceMomentumService,
    Depends(get_momentum_service),
]


@router.post(
    "/financial-performance/evaluate",
    response_model=SuccessResponse[FinancialPerformanceDimensionResponse],
    status_code=status.HTTP_200_OK,
    summary="Evaluate Financial Performance Business Momentum",
    description=(
        "Evaluates Financial Performance dimension movement and rate using "
        "AFPE v1.2 evidence under MOM-FD-012."
    ),
    responses={
        HTTPStatus.OK: {
            "description": (
                "Financial Performance dimension evaluated successfully."
            )
        },
        HTTPStatus.BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Request validation failed.",
        },
        HTTPStatus.UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Authentication is required.",
        },
        HTTPStatus.FORBIDDEN: {
            "model": ErrorResponse,
            "description": (
                "Caller is not authorized for the requested business scope."
            ),
        },
    },
)
async def evaluate_financial_performance(
    request: EvaluateFinancialPerformanceRequest,
    current_user: CurrentUser,
    momentum_service: MomentumServiceDependency,
) -> SuccessResponse[FinancialPerformanceDimensionResponse]:
    """Evaluate Financial Performance dimension for an authorized business."""
    obs_req = request.current_observation_context
    obs_context_req = ObservationContextRequest(
        granularity=obs_req.granularity,
        period_type=obs_req.period_type,
        period_start=obs_req.period_start,
        period_end=obs_req.period_end,
        observation_period_id=obs_req.observation_period_id,
        period_policy_id=obs_req.period_policy_id,
        period_policy_version=obs_req.period_policy_version,
        reconstruction_context_id=obs_req.reconstruction_context_id,
        as_of=obs_req.as_of,
    )

    auth_context = AuthorizationContext(principal_id=current_user.id)

    result = await momentum_service.evaluate_dimension(
        business_id=request.business_id,
        current_observation_context=obs_context_req,
        authorization_context=auth_context,
        evidence_perspective=request.evidence_perspective,
        requested_comparison_kind=request.requested_comparison_kind,
    )

    if any(lim.code == "UNAUTHORIZED_BUSINESS_SCOPE" for lim in result.limitations):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authorization does not permit the requested business scope.",
        )

    response_data = FinancialPerformanceDimensionResponse.from_domain(result)
    return SuccessResponse(
        success=True,
        message="Financial Performance Business Momentum evaluated successfully",
        data=response_data,
    )
