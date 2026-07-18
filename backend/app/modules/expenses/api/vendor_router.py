"""Expense vendor API router."""

import uuid
from http import HTTPStatus
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Query, Response, status

from app.common.pagination import PaginationParams
from app.core.responses import ErrorResponse, PaginatedApiResponse, SuccessResponse
from app.modules.business.exceptions import BusinessNotMemberException
from app.modules.expenses.api.dependencies import (
    get_expense_unit_of_work,
    get_vendor_service,
)
from app.modules.expenses.exceptions import VendorNotFoundException
from app.modules.expenses.models import Vendor
from app.modules.expenses.schemas import (
    VendorCreate,
    VendorListResponse,
    VendorResponse,
    VendorUpdate,
)
from app.modules.expenses.services import VendorService
from app.modules.identity.dependencies import CurrentUser

router = APIRouter(prefix="/expenses/vendors", tags=["Expense Vendors"])
VendorServiceDependency = Annotated[VendorService, Depends(get_vendor_service)]
ExpenseUnitOfWorkDependency = Annotated[Any, Depends(get_expense_unit_of_work)]


@router.post(
    "",
    response_model=SuccessResponse[VendorResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create vendor",
    description="Creates a vendor for a business the authenticated user belongs to.",
    responses={
        HTTPStatus.CREATED: {"description": "Vendor created successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def create_vendor(
    request: VendorCreate,
    current_user: CurrentUser,
    uow: ExpenseUnitOfWorkDependency,
    vendor_service: VendorServiceDependency,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[VendorResponse]:
    """Create a vendor."""
    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)

    vendor = await vendor_service.create_vendor(request, business_id=business_id)
    return SuccessResponse(
        success=True,
        message="Vendor created successfully",
        data=vendor,
    )


@router.get(
    "",
    response_model=PaginatedApiResponse[VendorListResponse],
    status_code=status.HTTP_200_OK,
    summary="List vendors",
    description="Lists vendors for a business the authenticated user belongs to.",
    responses={
        HTTPStatus.OK: {"description": "Vendors returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
    },
)
async def list_vendors(
    current_user: CurrentUser,
    uow: ExpenseUnitOfWorkDependency,
    vendor_service: VendorServiceDependency,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    page: Annotated[int, Query(ge=1, description="Page number.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page.")] = 20,
    sort: Annotated[
        str | None,
        Query(description="Sort field, e.g. name, -created_at."),
    ] = None,
) -> PaginatedApiResponse[VendorListResponse]:
    """List vendors."""
    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)

    vendor_page = await vendor_service.list_vendors(
        business_id,
        PaginationParams(page=page, size=page_size),
        sort=sort,
    )
    return PaginatedApiResponse(
        success=True,
        message="Vendors returned successfully",
        data=vendor_page.items,
        meta=vendor_page.meta,
    )


@router.get(
    "/{vendor_id}",
    response_model=SuccessResponse[VendorResponse],
    status_code=status.HTTP_200_OK,
    summary="Get vendor",
    description="Returns a vendor when the authenticated user belongs to its business.",
    responses={
        HTTPStatus.OK: {"description": "Vendor returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
    },
)
async def get_vendor(
    vendor_id: uuid.UUID,
    current_user: CurrentUser,
    uow: ExpenseUnitOfWorkDependency,
    vendor_service: VendorServiceDependency,
) -> SuccessResponse[VendorResponse]:
    """Return a vendor."""
    async with uow:
        await _get_vendor_for_user(uow, vendor_id, current_user.id)

    vendor = await vendor_service.get_vendor(vendor_id)
    return SuccessResponse(
        success=True,
        message="Vendor returned successfully",
        data=vendor,
    )


@router.patch(
    "/{vendor_id}",
    response_model=SuccessResponse[VendorResponse],
    status_code=status.HTTP_200_OK,
    summary="Update vendor",
    description="Updates a vendor when the authenticated user belongs to its business.",
    responses={
        HTTPStatus.OK: {"description": "Vendor updated successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def update_vendor(
    vendor_id: uuid.UUID,
    request: VendorUpdate,
    current_user: CurrentUser,
    uow: ExpenseUnitOfWorkDependency,
    vendor_service: VendorServiceDependency,
) -> SuccessResponse[VendorResponse]:
    """Update a vendor."""
    async with uow:
        await _get_vendor_for_user(uow, vendor_id, current_user.id)

    vendor = await vendor_service.update_vendor(vendor_id, request)
    return SuccessResponse(
        success=True,
        message="Vendor updated successfully",
        data=vendor,
    )


@router.delete(
    "/{vendor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate vendor",
    description=(
        "Deactivates a vendor when the authenticated user belongs to its business."
    ),
    responses={
        HTTPStatus.NO_CONTENT: {"description": "Vendor deactivated successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
    },
)
async def deactivate_vendor(
    vendor_id: uuid.UUID,
    current_user: CurrentUser,
    uow: ExpenseUnitOfWorkDependency,
    vendor_service: VendorServiceDependency,
) -> Response:
    """Deactivate a vendor."""
    async with uow:
        await _get_vendor_for_user(uow, vendor_id, current_user.id)

    await vendor_service.deactivate_vendor(vendor_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _ensure_business_member(
    uow: Any,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Raise when the current user is not a member of the business."""
    if not await uow.business_memberships.is_member(
        business_id=business_id,
        user_id=user_id,
    ):
        raise BusinessNotMemberException(
            "User is not a member of the business",
            details={"business_id": str(business_id), "user_id": str(user_id)},
        )


async def _get_vendor_for_user(
    uow: Any,
    vendor_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Vendor:
    """Return a vendor after enforcing business membership."""
    vendor = await uow.vendors.get_by_id(vendor_id)
    if vendor is None:
        raise VendorNotFoundException(
            "Vendor not found",
            details={"vendor_id": str(vendor_id)},
        )
    await _ensure_business_member(uow, vendor.business_id, user_id)
    return cast(Vendor, vendor)
