"""Purchase Management API router."""

import uuid
from datetime import date
from http import HTTPStatus
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Query, Response, status

from app.common.pagination import PaginationParams
from app.core.responses import ErrorResponse, PaginatedApiResponse, SuccessResponse
from app.modules.business.api.context import ensure_active_business_membership
from app.modules.identity.dependencies import CurrentUser
from app.modules.purchases.api.dependencies import (
    get_purchase_service,
    get_purchase_unit_of_work,
    get_supplier_service,
)
from app.modules.purchases.exceptions import (
    PurchaseNotFoundException,
    SupplierNotFoundException,
)
from app.modules.purchases.models import PurchaseInvoice, PurchaseStatus, Supplier
from app.modules.purchases.schemas import (
    PurchaseInvoiceCreate,
    PurchaseInvoiceListResponse,
    PurchaseInvoiceResponse,
    PurchaseInvoiceUpdate,
    SupplierCreate,
    SupplierListResponse,
    SupplierResponse,
    SupplierUpdate,
)
from app.modules.purchases.services import PurchaseService, SupplierService

router = APIRouter(prefix="/purchases", tags=["Purchases"])
SupplierServiceDependency = Annotated[SupplierService, Depends(get_supplier_service)]
PurchaseServiceDependency = Annotated[PurchaseService, Depends(get_purchase_service)]
PurchaseUnitOfWorkDependency = Annotated[Any, Depends(get_purchase_unit_of_work)]


@router.post(
    "/suppliers",
    response_model=SuccessResponse[SupplierResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create supplier",
    description="Creates a supplier for a business the authenticated user belongs to.",
    responses={
        HTTPStatus.CREATED: {"description": "Supplier created successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def create_supplier(
    request: SupplierCreate,
    current_user: CurrentUser,
    uow: PurchaseUnitOfWorkDependency,
    supplier_service: SupplierServiceDependency,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[SupplierResponse]:
    """Create a supplier."""
    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)

    supplier = await supplier_service.create_supplier(request, business_id=business_id)
    return SuccessResponse(
        success=True,
        message="Supplier created successfully",
        data=supplier,
    )


@router.get(
    "/suppliers",
    response_model=PaginatedApiResponse[SupplierListResponse],
    status_code=status.HTTP_200_OK,
    summary="List suppliers",
    description="Lists suppliers for a business the authenticated user belongs to.",
    responses={
        HTTPStatus.OK: {"description": "Suppliers returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
    },
)
async def list_suppliers(
    current_user: CurrentUser,
    uow: PurchaseUnitOfWorkDependency,
    supplier_service: SupplierServiceDependency,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    page: Annotated[int, Query(ge=1, description="Page number.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page.")] = 20,
    search: Annotated[
        str | None,
        Query(description="Search supplier name, code, or GSTIN."),
    ] = None,
    sort: Annotated[
        str | None,
        Query(description="Sort field, e.g. name, -created_at."),
    ] = None,
) -> PaginatedApiResponse[SupplierListResponse]:
    """List suppliers."""
    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)

    supplier_page = await supplier_service.list_suppliers(
        business_id,
        PaginationParams(page=page, size=page_size),
        sort=sort,
        search=search,
    )
    return PaginatedApiResponse(
        success=True,
        message="Suppliers returned successfully",
        data=supplier_page.items,
        meta=supplier_page.meta,
    )


@router.get(
    "/suppliers/{supplier_id}",
    response_model=SuccessResponse[SupplierResponse],
    status_code=status.HTTP_200_OK,
    summary="Get supplier",
    description=(
        "Returns a supplier when the authenticated user belongs to its business."
    ),
    responses={
        HTTPStatus.OK: {"description": "Supplier returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
    },
)
async def get_supplier(
    supplier_id: uuid.UUID,
    current_user: CurrentUser,
    uow: PurchaseUnitOfWorkDependency,
    supplier_service: SupplierServiceDependency,
) -> SuccessResponse[SupplierResponse]:
    """Return a supplier."""
    async with uow:
        await _get_supplier_for_user(uow, supplier_id, current_user.id)

    supplier = await supplier_service.get_supplier(supplier_id)
    return SuccessResponse(
        success=True,
        message="Supplier returned successfully",
        data=supplier,
    )


@router.patch(
    "/suppliers/{supplier_id}",
    response_model=SuccessResponse[SupplierResponse],
    status_code=status.HTTP_200_OK,
    summary="Update supplier",
    description=(
        "Updates a supplier when the authenticated user belongs to its business."
    ),
    responses={
        HTTPStatus.OK: {"description": "Supplier updated successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def update_supplier(
    supplier_id: uuid.UUID,
    request: SupplierUpdate,
    current_user: CurrentUser,
    uow: PurchaseUnitOfWorkDependency,
    supplier_service: SupplierServiceDependency,
) -> SuccessResponse[SupplierResponse]:
    """Update a supplier."""
    async with uow:
        await _get_supplier_for_user(uow, supplier_id, current_user.id)

    supplier = await supplier_service.update_supplier(supplier_id, request)
    return SuccessResponse(
        success=True,
        message="Supplier updated successfully",
        data=supplier,
    )


@router.delete(
    "/suppliers/{supplier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate supplier",
    description=(
        "Deactivates a supplier when the authenticated user belongs to its business."
    ),
    responses={
        HTTPStatus.NO_CONTENT: {"description": "Supplier deactivated successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
    },
)
async def deactivate_supplier(
    supplier_id: uuid.UUID,
    current_user: CurrentUser,
    uow: PurchaseUnitOfWorkDependency,
    supplier_service: SupplierServiceDependency,
) -> Response:
    """Deactivate a supplier."""
    async with uow:
        await _get_supplier_for_user(uow, supplier_id, current_user.id)

    await supplier_service.deactivate_supplier(supplier_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/suppliers/{supplier_id}/reactivate",
    response_model=SuccessResponse[SupplierResponse],
    status_code=status.HTTP_200_OK,
    summary="Reactivate supplier",
    description=(
        "Reactivates a supplier when the authenticated user belongs to its business."
    ),
    responses={
        HTTPStatus.OK: {"description": "Supplier reactivated successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
    },
)
async def reactivate_supplier(
    supplier_id: uuid.UUID,
    current_user: CurrentUser,
    uow: PurchaseUnitOfWorkDependency,
    supplier_service: SupplierServiceDependency,
) -> SuccessResponse[SupplierResponse]:
    """Reactivate a supplier."""
    async with uow:
        await _get_supplier_for_user(uow, supplier_id, current_user.id)

    supplier = await supplier_service.reactivate_supplier(supplier_id)
    return SuccessResponse(
        success=True,
        message="Supplier reactivated successfully",
        data=supplier,
    )


@router.post(
    "",
    response_model=SuccessResponse[PurchaseInvoiceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create purchase",
    description="Creates a purchase invoice for a business member.",
    responses={
        HTTPStatus.CREATED: {"description": "Purchase created successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def create_purchase(
    request: PurchaseInvoiceCreate,
    current_user: CurrentUser,
    uow: PurchaseUnitOfWorkDependency,
    purchase_service: PurchaseServiceDependency,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[PurchaseInvoiceResponse]:
    """Create a purchase invoice."""
    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)

    purchase = await purchase_service.create_purchase(
        request,
        business_id=business_id,
    )
    return SuccessResponse(
        success=True,
        message="Purchase created successfully",
        data=purchase,
    )


@router.get(
    "",
    response_model=PaginatedApiResponse[PurchaseInvoiceListResponse],
    status_code=status.HTTP_200_OK,
    summary="List purchases",
    description="Lists purchase invoices for a business member.",
    responses={
        HTTPStatus.OK: {"description": "Purchases returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
    },
)
async def list_purchases(
    current_user: CurrentUser,
    uow: PurchaseUnitOfWorkDependency,
    purchase_service: PurchaseServiceDependency,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    page: Annotated[int, Query(ge=1, description="Page number.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page.")] = 20,
    sort: Annotated[
        str | None,
        Query(description="Sort field, e.g. invoice_date, supplier_name."),
    ] = None,
    search: Annotated[
        str | None,
        Query(description="Search purchase number, invoice number, or notes."),
    ] = None,
    supplier_id: Annotated[
        uuid.UUID | None,
        Query(alias="supplier", description="Optional supplier UUID filter."),
    ] = None,
    status_filter: Annotated[
        PurchaseStatus | None,
        Query(alias="status", description="Optional purchase status filter."),
    ] = None,
    invoice_date_from: Annotated[
        date | None,
        Query(description="Optional inclusive invoice date lower bound."),
    ] = None,
    invoice_date_to: Annotated[
        date | None,
        Query(description="Optional inclusive invoice date upper bound."),
    ] = None,
    due_date_from: Annotated[
        date | None,
        Query(description="Optional inclusive due date lower bound."),
    ] = None,
    due_date_to: Annotated[
        date | None,
        Query(description="Optional inclusive due date upper bound."),
    ] = None,
) -> PaginatedApiResponse[PurchaseInvoiceListResponse]:
    """List purchase invoices."""
    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)

    purchase_page = await purchase_service.list_purchases(
        business_id,
        PaginationParams(page=page, size=page_size),
        sort=sort,
        supplier_id=supplier_id,
        status=status_filter,
        invoice_date_from=invoice_date_from,
        invoice_date_to=invoice_date_to,
        due_date_from=due_date_from,
        due_date_to=due_date_to,
        search=search,
    )
    return PaginatedApiResponse(
        success=True,
        message="Purchases returned successfully",
        data=[
            PurchaseInvoiceListResponse.model_validate(purchase)
            for purchase in purchase_page.items
        ],
        meta=purchase_page.meta,
    )


@router.get(
    "/{purchase_id}",
    response_model=SuccessResponse[PurchaseInvoiceResponse],
    status_code=status.HTTP_200_OK,
    summary="Get purchase",
    description="Returns a purchase invoice for a business member.",
    responses={
        HTTPStatus.OK: {"description": "Purchase returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
    },
)
async def get_purchase(
    purchase_id: uuid.UUID,
    current_user: CurrentUser,
    uow: PurchaseUnitOfWorkDependency,
    purchase_service: PurchaseServiceDependency,
) -> SuccessResponse[PurchaseInvoiceResponse]:
    """Return a purchase invoice."""
    async with uow:
        await _get_purchase_for_user(uow, purchase_id, current_user.id)

    purchase = await purchase_service.get_purchase(purchase_id)
    return SuccessResponse(
        success=True,
        message="Purchase returned successfully",
        data=purchase,
    )


@router.patch(
    "/{purchase_id}",
    response_model=SuccessResponse[PurchaseInvoiceResponse],
    status_code=status.HTTP_200_OK,
    summary="Update purchase",
    description="Updates a purchase invoice for a business member.",
    responses={
        HTTPStatus.OK: {"description": "Purchase updated successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def update_purchase(
    purchase_id: uuid.UUID,
    request: PurchaseInvoiceUpdate,
    current_user: CurrentUser,
    uow: PurchaseUnitOfWorkDependency,
    purchase_service: PurchaseServiceDependency,
) -> SuccessResponse[PurchaseInvoiceResponse]:
    """Update a purchase invoice."""
    async with uow:
        await _get_purchase_for_user(uow, purchase_id, current_user.id)

    purchase = await purchase_service.update_purchase(purchase_id, request)
    return SuccessResponse(
        success=True,
        message="Purchase updated successfully",
        data=purchase,
    )


@router.post(
    "/{purchase_id}/approve",
    response_model=SuccessResponse[PurchaseInvoiceResponse],
    status_code=status.HTTP_200_OK,
    summary="Approve purchase",
    description="Approves a draft purchase invoice for a business member.",
)
async def approve_purchase(
    purchase_id: uuid.UUID,
    current_user: CurrentUser,
    uow: PurchaseUnitOfWorkDependency,
    purchase_service: PurchaseServiceDependency,
) -> SuccessResponse[PurchaseInvoiceResponse]:
    """Approve a purchase invoice."""
    async with uow:
        await _get_purchase_for_user(uow, purchase_id, current_user.id)

    purchase = await purchase_service.approve_purchase(purchase_id)
    return SuccessResponse(
        success=True,
        message="Purchase approved successfully",
        data=purchase,
    )


@router.post(
    "/{purchase_id}/receive",
    response_model=SuccessResponse[PurchaseInvoiceResponse],
    status_code=status.HTTP_200_OK,
    summary="Mark purchase received",
    description="Marks an approved purchase invoice as received.",
)
async def mark_purchase_received(
    purchase_id: uuid.UUID,
    current_user: CurrentUser,
    uow: PurchaseUnitOfWorkDependency,
    purchase_service: PurchaseServiceDependency,
) -> SuccessResponse[PurchaseInvoiceResponse]:
    """Mark a purchase invoice received."""
    async with uow:
        await _get_purchase_for_user(uow, purchase_id, current_user.id)

    purchase = await purchase_service.mark_received(purchase_id)
    return SuccessResponse(
        success=True,
        message="Purchase marked received successfully",
        data=purchase,
    )


@router.post(
    "/{purchase_id}/pay",
    response_model=SuccessResponse[PurchaseInvoiceResponse],
    status_code=status.HTTP_200_OK,
    summary="Mark purchase paid",
    description="Marks a received purchase invoice as paid.",
)
async def mark_purchase_paid(
    purchase_id: uuid.UUID,
    current_user: CurrentUser,
    uow: PurchaseUnitOfWorkDependency,
    purchase_service: PurchaseServiceDependency,
) -> SuccessResponse[PurchaseInvoiceResponse]:
    """Mark a purchase invoice paid."""
    async with uow:
        await _get_purchase_for_user(uow, purchase_id, current_user.id)

    purchase = await purchase_service.mark_paid(purchase_id)
    return SuccessResponse(
        success=True,
        message="Purchase marked paid successfully",
        data=purchase,
    )


@router.post(
    "/{purchase_id}/cancel",
    response_model=SuccessResponse[PurchaseInvoiceResponse],
    status_code=status.HTTP_200_OK,
    summary="Cancel purchase",
    description="Cancels a purchase invoice before payment.",
)
async def cancel_purchase(
    purchase_id: uuid.UUID,
    current_user: CurrentUser,
    uow: PurchaseUnitOfWorkDependency,
    purchase_service: PurchaseServiceDependency,
) -> SuccessResponse[PurchaseInvoiceResponse]:
    """Cancel a purchase invoice."""
    async with uow:
        await _get_purchase_for_user(uow, purchase_id, current_user.id)

    purchase = await purchase_service.cancel_purchase(purchase_id)
    return SuccessResponse(
        success=True,
        message="Purchase cancelled successfully",
        data=purchase,
    )


async def _ensure_business_member(
    uow: Any,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Raise when the current user is not a member of the business."""
    await ensure_active_business_membership(
        uow,
        business_id=business_id,
        user_id=user_id,
        entered=True,
    )


async def _get_supplier_for_user(
    uow: Any,
    supplier_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Supplier:
    """Return a supplier after enforcing business membership."""
    supplier = await uow.suppliers.get_by_id(supplier_id)
    if supplier is None:
        raise SupplierNotFoundException(
            "Supplier not found",
            details={"supplier_id": str(supplier_id)},
        )
    await _ensure_business_member(uow, supplier.business_id, user_id)
    return cast(Supplier, supplier)


async def _get_purchase_for_user(
    uow: Any,
    purchase_id: uuid.UUID,
    user_id: uuid.UUID,
) -> PurchaseInvoice:
    """Return a purchase invoice after enforcing business membership."""
    purchase = await uow.purchase_invoices.get_by_id(purchase_id)
    if purchase is None:
        raise PurchaseNotFoundException(
            "Purchase invoice not found",
            details={"purchase_id": str(purchase_id)},
        )
    await _ensure_business_member(uow, purchase.business_id, user_id)
    return cast(PurchaseInvoice, purchase)
