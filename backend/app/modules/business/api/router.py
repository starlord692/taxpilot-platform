"""Business API router."""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.common.pagination import PaginationParams
from app.core.responses import ErrorResponse, PaginatedApiResponse, SuccessResponse
from app.modules.business.api.dependencies import get_business_service
from app.modules.business.schemas import (
    BusinessResponse,
    BusinessSummaryResponse,
    CreateBusinessRequest,
    UpdateBusinessRequest,
)
from app.modules.business.services import BusinessService
from app.modules.identity.dependencies import CurrentUser

router = APIRouter(prefix="/businesses", tags=["Businesses"])
BusinessServiceDependency = Annotated[
    BusinessService,
    Depends(get_business_service),
]


@router.post(
    "/",
    response_model=SuccessResponse[BusinessResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create business",
    description="Creates a business and assigns the authenticated user as owner.",
    responses={
        HTTPStatus.CREATED: {
            "description": "Business created successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Business created successfully",
                        "data": {
                            "id": "018f1d3c-4f87-7b6f-8f25-6cfcdd17f8b4",
                            "legal_name": "TaxPilot Labs Private Limited",
                            "trade_name": "TaxPilot Labs",
                            "business_type": "private_limited",
                            "registration_status": "registered",
                            "business_email": "accounts@example.com",
                            "business_phone": "+919876543210",
                            "website": "https://example.com",
                            "logo_url": None,
                            "status": "active",
                            "address": None,
                            "tax_profile": None,
                            "settings": None,
                        },
                    }
                }
            },
        },
        HTTPStatus.BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Request validation failed.",
        },
        HTTPStatus.UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Authentication is required.",
        },
        HTTPStatus.CONFLICT: {
            "model": ErrorResponse,
            "description": "Business already exists.",
        },
    },
)
async def create_business(
    request: CreateBusinessRequest,
    current_user: CurrentUser,
    business_service: BusinessServiceDependency,
) -> SuccessResponse[BusinessResponse]:
    """Create a business for the current user."""
    business = await business_service.create_business(request, current_user.id)
    return SuccessResponse(
        success=True,
        message="Business created successfully",
        data=business,
    )


@router.get(
    "/",
    response_model=PaginatedApiResponse[BusinessSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="List businesses",
    description="Lists businesses that the authenticated user belongs to.",
    responses={
        HTTPStatus.OK: {"description": "Businesses returned successfully."},
        HTTPStatus.UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Authentication is required.",
        },
    },
)
async def list_businesses(
    current_user: CurrentUser,
    business_service: BusinessServiceDependency,
    page: Annotated[int, Query(ge=1, description="Page number.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page.")] = 20,
    search: Annotated[
        str | None,
        Query(description="Optional legal-name search text."),
    ] = None,
    sort: Annotated[
        str | None,
        Query(description="Sort field, e.g. created_at, -created_at, legal_name."),
    ] = None,
) -> PaginatedApiResponse[BusinessSummaryResponse]:
    """List businesses for the current user."""
    business_page = await business_service.list_businesses(
        current_user.id,
        PaginationParams(page=page, size=page_size),
        search=search,
        sort=sort,
    )
    return PaginatedApiResponse(
        success=True,
        message="Businesses returned successfully",
        data=business_page.items,
        meta=business_page.meta,
    )


@router.get(
    "/{business_code}",
    response_model=SuccessResponse[BusinessResponse],
    status_code=status.HTTP_200_OK,
    summary="Get business",
    description="Returns a business when the authenticated user is a member.",
    responses={
        HTTPStatus.OK: {"description": "Business returned successfully."},
        HTTPStatus.UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Authentication is required.",
        },
        HTTPStatus.FORBIDDEN: {
            "model": ErrorResponse,
            "description": "User is not a business member.",
        },
        HTTPStatus.NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Business was not found.",
        },
    },
)
async def get_business(
    business_code: str,
    current_user: CurrentUser,
    business_service: BusinessServiceDependency,
) -> SuccessResponse[BusinessResponse]:
    """Return a business by code."""
    business = await business_service.get_business(business_code, current_user.id)
    return SuccessResponse(
        success=True,
        message="Business returned successfully",
        data=business,
    )


@router.patch(
    "/{business_code}",
    response_model=SuccessResponse[BusinessResponse],
    status_code=status.HTTP_200_OK,
    summary="Update business",
    description="Updates a business when the authenticated user is a member.",
    responses={
        HTTPStatus.OK: {"description": "Business updated successfully."},
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
            "description": "User is not a business member.",
        },
        HTTPStatus.NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Business was not found.",
        },
    },
)
async def update_business(
    business_code: str,
    request: UpdateBusinessRequest,
    current_user: CurrentUser,
    business_service: BusinessServiceDependency,
) -> SuccessResponse[BusinessResponse]:
    """Update a business by code."""
    business = await business_service.update_business_by_code(
        business_code,
        request,
        current_user.id,
    )
    return SuccessResponse(
        success=True,
        message="Business updated successfully",
        data=business,
    )


@router.delete(
    "/{business_code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive business",
    description="Archives a business when the authenticated user is a member.",
    responses={
        HTTPStatus.NO_CONTENT: {"description": "Business archived successfully."},
        HTTPStatus.UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Authentication is required.",
        },
        HTTPStatus.FORBIDDEN: {
            "model": ErrorResponse,
            "description": "User is not a business member.",
        },
        HTTPStatus.NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Business was not found.",
        },
    },
)
async def archive_business(
    business_code: str,
    current_user: CurrentUser,
    business_service: BusinessServiceDependency,
) -> Response:
    """Archive a business by code."""
    await business_service.archive_business_by_code(business_code, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
