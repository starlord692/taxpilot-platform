"""Inventory warehouse API router."""

import uuid
from http import HTTPStatus
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Query, status

from app.common.pagination import PaginationParams
from app.core.responses import ErrorResponse, PaginatedApiResponse, SuccessResponse
from app.modules.business.api.context import ensure_active_business_membership
from app.modules.identity.dependencies import CurrentUser
from app.modules.inventory.api.dependencies import (
    get_inventory_unit_of_work,
    get_warehouse_service,
)
from app.modules.inventory.exceptions import WarehouseNotFoundException
from app.modules.inventory.models import Warehouse
from app.modules.inventory.schemas import (
    WarehouseCreate,
    WarehouseListResponse,
    WarehouseResponse,
    WarehouseUpdate,
)
from app.modules.inventory.services import WarehouseService

router = APIRouter(prefix="/inventory/warehouses", tags=["Inventory Warehouses"])
WarehouseServiceDependency = Annotated[WarehouseService, Depends(get_warehouse_service)]
InventoryUnitOfWorkDependency = Annotated[Any, Depends(get_inventory_unit_of_work)]


@router.post(
    "",
    response_model=SuccessResponse[WarehouseResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create warehouse",
    description="Creates an inventory warehouse for a business member.",
    responses={
        HTTPStatus.CREATED: {"description": "Warehouse created successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def create_warehouse(
    request: WarehouseCreate,
    current_user: CurrentUser,
    uow: InventoryUnitOfWorkDependency,
    warehouse_service: WarehouseServiceDependency,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[WarehouseResponse]:
    """Create an inventory warehouse."""
    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)

    warehouse = await warehouse_service.create_warehouse(
        request,
        business_id=business_id,
    )
    return SuccessResponse(
        success=True,
        message="Warehouse created successfully",
        data=warehouse,
    )


@router.get(
    "",
    response_model=PaginatedApiResponse[WarehouseListResponse],
    status_code=status.HTTP_200_OK,
    summary="List warehouses",
    description="Lists inventory warehouses for a business member.",
    responses={
        HTTPStatus.OK: {"description": "Warehouses returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
    },
)
async def list_warehouses(
    current_user: CurrentUser,
    uow: InventoryUnitOfWorkDependency,
    warehouse_service: WarehouseServiceDependency,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    page: Annotated[int, Query(ge=1, description="Page number.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page.")] = 20,
    code: Annotated[str | None, Query(description="Filter by warehouse code.")] = None,
    name: Annotated[str | None, Query(description="Filter by warehouse name.")] = None,
    active: Annotated[bool | None, Query(description="Filter by active flag.")] = None,
    sort: Annotated[
        str | None,
        Query(description="Sort field, e.g. code, name, -created_at."),
    ] = None,
) -> PaginatedApiResponse[WarehouseListResponse]:
    """List inventory warehouses."""
    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)

    warehouse_page = await warehouse_service.list_warehouses(
        business_id,
        PaginationParams(page=page, size=page_size),
        sort=sort,
        code=code,
        name=name,
        is_active=active,
    )
    return PaginatedApiResponse(
        success=True,
        message="Warehouses returned successfully",
        data=warehouse_page.items,
        meta=warehouse_page.meta,
    )


@router.get(
    "/{warehouse_id}",
    response_model=SuccessResponse[WarehouseResponse],
    status_code=status.HTTP_200_OK,
    summary="Get warehouse",
    description=(
        "Returns a warehouse when the authenticated user belongs to its business."
    ),
    responses={
        HTTPStatus.OK: {"description": "Warehouse returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
    },
)
async def get_warehouse(
    warehouse_id: uuid.UUID,
    current_user: CurrentUser,
    uow: InventoryUnitOfWorkDependency,
    warehouse_service: WarehouseServiceDependency,
) -> SuccessResponse[WarehouseResponse]:
    """Return an inventory warehouse."""
    async with uow:
        warehouse = await _get_warehouse_for_user(uow, warehouse_id, current_user.id)

    warehouse_response = await warehouse_service.get_warehouse(
        warehouse_id,
        business_id=warehouse.business_id,
    )
    return SuccessResponse(
        success=True,
        message="Warehouse returned successfully",
        data=warehouse_response,
    )


@router.patch(
    "/{warehouse_id}",
    response_model=SuccessResponse[WarehouseResponse],
    status_code=status.HTTP_200_OK,
    summary="Update warehouse",
    description=(
        "Updates a warehouse when the authenticated user belongs to its business."
    ),
    responses={
        HTTPStatus.OK: {"description": "Warehouse updated successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def update_warehouse(
    warehouse_id: uuid.UUID,
    request: WarehouseUpdate,
    current_user: CurrentUser,
    uow: InventoryUnitOfWorkDependency,
    warehouse_service: WarehouseServiceDependency,
) -> SuccessResponse[WarehouseResponse]:
    """Update an inventory warehouse."""
    async with uow:
        warehouse = await _get_warehouse_for_user(uow, warehouse_id, current_user.id)

    warehouse_response = await warehouse_service.update_warehouse(
        warehouse_id,
        request,
        business_id=warehouse.business_id,
    )
    return SuccessResponse(
        success=True,
        message="Warehouse updated successfully",
        data=warehouse_response,
    )


@router.post(
    "/{warehouse_id}/activate",
    response_model=SuccessResponse[WarehouseResponse],
    status_code=status.HTTP_200_OK,
    summary="Activate warehouse",
    description=(
        "Activates a warehouse when the authenticated user belongs to its business."
    ),
    responses={
        HTTPStatus.OK: {"description": "Warehouse activated successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
    },
)
async def activate_warehouse(
    warehouse_id: uuid.UUID,
    current_user: CurrentUser,
    uow: InventoryUnitOfWorkDependency,
    warehouse_service: WarehouseServiceDependency,
) -> SuccessResponse[WarehouseResponse]:
    """Activate an inventory warehouse."""
    async with uow:
        warehouse = await _get_warehouse_for_user(uow, warehouse_id, current_user.id)

    warehouse_response = await warehouse_service.activate_warehouse(
        warehouse_id,
        business_id=warehouse.business_id,
    )
    return SuccessResponse(
        success=True,
        message="Warehouse activated successfully",
        data=warehouse_response,
    )


@router.post(
    "/{warehouse_id}/deactivate",
    response_model=SuccessResponse[WarehouseResponse],
    status_code=status.HTTP_200_OK,
    summary="Deactivate warehouse",
    description=(
        "Deactivates a warehouse when the authenticated user belongs to its business."
    ),
    responses={
        HTTPStatus.OK: {"description": "Warehouse deactivated successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
    },
)
async def deactivate_warehouse(
    warehouse_id: uuid.UUID,
    current_user: CurrentUser,
    uow: InventoryUnitOfWorkDependency,
    warehouse_service: WarehouseServiceDependency,
) -> SuccessResponse[WarehouseResponse]:
    """Deactivate an inventory warehouse."""
    async with uow:
        warehouse = await _get_warehouse_for_user(uow, warehouse_id, current_user.id)

    warehouse_response = await warehouse_service.deactivate_warehouse(
        warehouse_id,
        business_id=warehouse.business_id,
    )
    return SuccessResponse(
        success=True,
        message="Warehouse deactivated successfully",
        data=warehouse_response,
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


async def _get_warehouse_for_user(
    uow: Any,
    warehouse_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Warehouse:
    """Return a warehouse after enforcing business membership."""
    warehouse = await uow.warehouses.get_by_id(warehouse_id)
    if warehouse is None:
        raise WarehouseNotFoundException(
            "Warehouse not found",
            details={"warehouse_id": str(warehouse_id)},
        )
    await _ensure_business_member(uow, warehouse.business_id, user_id)
    return cast(Warehouse, warehouse)
