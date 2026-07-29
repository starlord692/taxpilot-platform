"""Document automation API router."""

import uuid
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, status

from app.core.responses import ErrorResponse, SuccessResponse
from app.modules.business.api.context import ensure_active_business_membership
from app.modules.business.exceptions import BusinessNotMemberException
from app.modules.documents.automation.api.dependencies import (
    get_automation_unit_of_work,
    get_document_automation_service,
)
from app.modules.documents.automation.schemas import (
    AutomationRequest,
    AutomationResult,
    AutomationRunResponse,
)
from app.modules.documents.automation.services import DocumentAutomationService
from app.modules.identity.dependencies import CurrentUser

router = APIRouter(prefix="/documents", tags=["Document Automation"])
AutomationServiceDep = Annotated[
    DocumentAutomationService,
    Depends(get_document_automation_service),
]
AutomationUnitOfWorkDep = Annotated[Any, Depends(get_automation_unit_of_work)]


@router.post(
    "/{document_id}/automate",
    response_model=SuccessResponse[AutomationResult],
    status_code=status.HTTP_200_OK,
    summary="Automate reviewed document",
    description=(
        "Delegates an approved reviewed document to the appropriate existing ERP "
        "service without duplicating ERP business logic."
    ),
    responses={
        HTTPStatus.OK: {"description": "Document automation completed."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def automate_document(
    document_id: uuid.UUID,
    request: AutomationRequest,
    current_user: CurrentUser,
    uow: AutomationUnitOfWorkDep,
    service: AutomationServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    idempotency_header: Annotated[
        str | None,
        Header(alias="Idempotency-Key", description="Idempotency key."),
    ] = None,
) -> SuccessResponse[AutomationResult]:
    """Automate a reviewed document."""
    await _ensure_business_member(uow, business_id, current_user.id)
    result = await service.automate(
        document_id,
        business_id=business_id,
        idempotency_key=request.idempotency_key or idempotency_header,
    )
    return SuccessResponse(
        success=True,
        message="Document automation completed successfully",
        data=result,
    )


@router.get(
    "/{document_id}/automation",
    response_model=SuccessResponse[AutomationRunResponse],
    status_code=status.HTTP_200_OK,
    summary="Get document automation state",
    description="Returns the latest automation run for a reviewed document.",
    responses={
        HTTPStatus.OK: {"description": "Document automation returned."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
    },
)
async def get_document_automation(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    uow: AutomationUnitOfWorkDep,
    service: AutomationServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[AutomationRunResponse]:
    """Return document automation state."""
    await _ensure_business_member(uow, business_id, current_user.id)
    run = await service.get_automation(document_id)
    if run.business_id != business_id:
        raise BusinessNotMemberException(
            "Document automation does not belong to the requested business",
            details={
                "document_business_id": str(run.business_id),
                "requested_business_id": str(business_id),
            },
        )
    return SuccessResponse(
        success=True,
        message="Document automation returned successfully",
        data=run,
    )


async def _ensure_business_member(
    uow: Any,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Raise when current user is not a business member."""
    async with uow:
        await ensure_active_business_membership(
            uow,
            business_id=business_id,
            user_id=user_id,
            entered=True,
        )
