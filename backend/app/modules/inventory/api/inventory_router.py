"""Inventory stock API router."""

import uuid
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app.common.pagination import PaginationParams
from app.core.responses import ErrorResponse, PaginatedApiResponse, SuccessResponse
from app.modules.business.api.context import ensure_active_business_membership
from app.modules.identity.dependencies import CurrentUser
from app.modules.inventory.api.dependencies import (
    get_inventory_service,
    get_inventory_unit_of_work,
)
from app.modules.inventory.exceptions import (
    ProductNotFoundException,
    WarehouseNotFoundException,
)
from app.modules.inventory.schemas import (
    ProductListResponse,
    StockBalanceListResponse,
    StockBalanceResponse,
)
from app.modules.inventory.services import InventoryService

router = APIRouter(prefix="/inventory", tags=["Inventory"])
InventoryServiceDependency = Annotated[InventoryService, Depends(get_inventory_service)]
InventoryUnitOfWorkDependency = Annotated[Any, Depends(get_inventory_unit_of_work)]


@router.get(
    "/stock",
    response_model=PaginatedApiResponse[StockBalanceListResponse],
    status_code=status.HTTP_200_OK,
    summary="List stock balances",
    description="Lists stock balances for a business member.",
    responses={
        HTTPStatus.OK: {"description": "Stock balances returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
    },
)
async def list_stock(
    current_user: CurrentUser,
    uow: InventoryUnitOfWorkDependency,
    inventory_service: InventoryServiceDependency,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    page: Annotated[int, Query(ge=1, description="Page number.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page.")] = 20,
    product_id: Annotated[uuid.UUID | None, Query(description="Product UUID.")] = None,
    warehouse_id: Annotated[
        uuid.UUID | None,
        Query(description="Warehouse UUID."),
    ] = None,
    movement_type: Annotated[
        str | None,
        Query(description="Future-compatible movement type filter."),
    ] = None,
    sort: Annotated[
        str | None,
        Query(description="Future-compatible sort field, e.g. updated_at."),
    ] = None,
) -> PaginatedApiResponse[StockBalanceListResponse]:
    """List stock balances."""
    _ = movement_type
    _ = sort
    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)

    balance_page = await inventory_service.list_stock_balances(
        business_id,
        PaginationParams(page=page, size=page_size),
        product_id=product_id,
        warehouse_id=warehouse_id,
    )
    return PaginatedApiResponse(
        success=True,
        message="Stock balances returned successfully",
        data=balance_page.items,
        meta=balance_page.meta,
    )


@router.get(
    "/products/{product_id}/stock",
    response_model=SuccessResponse[list[StockBalanceResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get product stock",
    description="Returns stock balances for a product within an accessible business.",
    responses={
        HTTPStatus.OK: {"description": "Product stock returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
    },
)
async def get_product_stock(
    product_id: uuid.UUID,
    current_user: CurrentUser,
    uow: InventoryUnitOfWorkDependency,
    inventory_service: InventoryServiceDependency,
) -> SuccessResponse[list[StockBalanceResponse]]:
    """Return stock balances for a product."""
    async with uow:
        product = await uow.products.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundException(
                "Product not found",
                details={"product_id": str(product_id)},
            )
        await _ensure_business_member(uow, product.business_id, current_user.id)
        business_id = product.business_id

    balances = await inventory_service.get_product_stock(
        product_id,
        business_id=business_id,
    )
    return SuccessResponse(
        success=True,
        message="Product stock returned successfully",
        data=balances,
    )


@router.get(
    "/warehouses/{warehouse_id}/stock",
    response_model=PaginatedApiResponse[StockBalanceListResponse],
    status_code=status.HTTP_200_OK,
    summary="Get warehouse stock",
    description="Returns stock balances for a warehouse within an accessible business.",
    responses={
        HTTPStatus.OK: {"description": "Warehouse stock returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
    },
)
async def get_warehouse_stock(
    warehouse_id: uuid.UUID,
    current_user: CurrentUser,
    uow: InventoryUnitOfWorkDependency,
    inventory_service: InventoryServiceDependency,
    page: Annotated[int, Query(ge=1, description="Page number.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page.")] = 20,
) -> PaginatedApiResponse[StockBalanceListResponse]:
    """Return stock balances for a warehouse."""
    async with uow:
        warehouse = await uow.warehouses.get_by_id(warehouse_id)
        if warehouse is None:
            raise WarehouseNotFoundException(
                "Warehouse not found",
                details={"warehouse_id": str(warehouse_id)},
            )
        await _ensure_business_member(uow, warehouse.business_id, current_user.id)
        business_id = warehouse.business_id

    balance_page = await inventory_service.get_warehouse_stock(
        warehouse_id,
        business_id=business_id,
        pagination=PaginationParams(page=page, size=page_size),
    )
    return PaginatedApiResponse(
        success=True,
        message="Warehouse stock returned successfully",
        data=balance_page.items,
        meta=balance_page.meta,
    )


@router.get(
    "/search",
    response_model=PaginatedApiResponse[ProductListResponse],
    status_code=status.HTTP_200_OK,
    summary="Search inventory",
    description="Searches inventory products for a business member.",
    responses={
        HTTPStatus.OK: {"description": "Inventory search returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
    },
)
async def search_inventory(
    current_user: CurrentUser,
    uow: InventoryUnitOfWorkDependency,
    inventory_service: InventoryServiceDependency,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    query: Annotated[str, Query(min_length=1, description="Search query.")],
    page: Annotated[int, Query(ge=1, description="Page number.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page.")] = 20,
) -> PaginatedApiResponse[ProductListResponse]:
    """Search inventory products."""
    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)

    search_page = await inventory_service.search_inventory(
        business_id,
        query,
        PaginationParams(page=page, size=page_size),
    )
    return PaginatedApiResponse(
        success=True,
        message="Inventory search returned successfully",
        data=search_page.items,
        meta=search_page.meta,
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
