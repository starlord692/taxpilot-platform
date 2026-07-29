"""Document validation and human review API router."""

import uuid
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app.common.pagination import PaginationParams
from app.core.responses import ErrorResponse, PaginatedApiResponse, SuccessResponse
from app.modules.business.api.context import ensure_active_business_membership
from app.modules.business.exceptions import BusinessNotMemberException
from app.modules.documents.review.api.dependencies import (
    get_document_review_service,
    get_review_unit_of_work,
)
from app.modules.documents.review.schemas import (
    DocumentReviewRequest,
    DocumentReviewResponse,
    DocumentValidationResponse,
)
from app.modules.documents.review.services import DocumentReviewService
from app.modules.identity.dependencies import CurrentUser

router = APIRouter(prefix="/documents", tags=["Document Review"])
ReviewServiceDep = Annotated[
    DocumentReviewService,
    Depends(get_document_review_service),
]
ReviewUnitOfWorkDep = Annotated[Any, Depends(get_review_unit_of_work)]


@router.post(
    "/{document_id}/validate",
    response_model=SuccessResponse[DocumentValidationResponse],
    status_code=status.HTTP_200_OK,
    summary="Validate extracted document",
    description=(
        "Runs business validation and matching checks for an extracted document "
        "without creating ERP records."
    ),
    responses={
        HTTPStatus.OK: {"description": "Document validation completed."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def validate_document(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    uow: ReviewUnitOfWorkDep,
    service: ReviewServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[DocumentValidationResponse]:
    """Validate extracted document data."""
    await _ensure_business_member(uow, business_id, current_user.id)
    validation = await service.validate(document_id)
    _ensure_document_business(validation.business_id, business_id)
    return SuccessResponse(
        success=True,
        message="Document validation completed successfully",
        data=validation,
    )


@router.get(
    "/{document_id}/validation",
    response_model=SuccessResponse[DocumentValidationResponse],
    status_code=status.HTTP_200_OK,
    summary="Get document validation",
    description="Returns validation issues, review state, and revision history.",
    responses={
        HTTPStatus.OK: {"description": "Document validation returned."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
    },
)
async def get_document_validation(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    uow: ReviewUnitOfWorkDep,
    service: ReviewServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[DocumentValidationResponse]:
    """Return validation and review state."""
    await _ensure_business_member(uow, business_id, current_user.id)
    validation = await service.get_validation(document_id)
    _ensure_document_business(validation.business_id, business_id)
    return SuccessResponse(
        success=True,
        message="Document validation returned successfully",
        data=validation,
    )


@router.post(
    "/{document_id}/review",
    response_model=SuccessResponse[DocumentValidationResponse],
    status_code=status.HTTP_200_OK,
    summary="Submit document review",
    description=(
        "Approves, rejects, or requests correction for a validated document. "
        "Manual corrections create immutable revision history."
    ),
    responses={
        HTTPStatus.OK: {"description": "Document review saved."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def review_document(
    document_id: uuid.UUID,
    request: DocumentReviewRequest,
    current_user: CurrentUser,
    uow: ReviewUnitOfWorkDep,
    service: ReviewServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[DocumentValidationResponse]:
    """Submit a human review decision."""
    await _ensure_business_member(uow, business_id, current_user.id)
    validation = await service.review(
        document_id,
        request,
        reviewed_by=current_user.id,
    )
    _ensure_document_business(validation.business_id, business_id)
    return SuccessResponse(
        success=True,
        message="Document review saved successfully",
        data=validation,
    )


@router.get(
    "/review/pending",
    response_model=PaginatedApiResponse[DocumentReviewResponse],
    status_code=status.HTTP_200_OK,
    summary="List pending document reviews",
    description="Lists pending review records for a business member.",
    responses={
        HTTPStatus.OK: {"description": "Pending reviews returned."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
    },
)
async def list_pending_reviews(
    current_user: CurrentUser,
    uow: ReviewUnitOfWorkDep,
    service: ReviewServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    page: Annotated[int, Query(ge=1, description="Page number.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page.")] = 20,
) -> PaginatedApiResponse[DocumentReviewResponse]:
    """List pending document reviews."""
    await _ensure_business_member(uow, business_id, current_user.id)
    review_page = await service.list_pending(
        business_id,
        PaginationParams(page=page, size=page_size),
    )
    return PaginatedApiResponse(
        success=True,
        message="Pending document reviews returned successfully",
        data=review_page.items,
        meta=review_page.meta,
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


def _ensure_document_business(
    document_business_id: uuid.UUID,
    requested_business_id: uuid.UUID,
) -> None:
    """Raise when document does not belong to requested business."""
    if document_business_id != requested_business_id:
        raise BusinessNotMemberException(
            "Document review does not belong to the requested business",
            details={
                "document_business_id": str(document_business_id),
                "requested_business_id": str(requested_business_id),
            },
        )
