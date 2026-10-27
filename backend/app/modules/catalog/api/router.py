"""Catalog API router."""

import uuid
from http import HTTPStatus
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Query, status

from app.common.pagination import PaginationParams
from app.core.responses import ErrorResponse, PaginatedApiResponse, SuccessResponse
from app.modules.business.exceptions import BusinessNotMemberException
from app.modules.catalog.api.dependencies import (
    get_catalog_service,
    get_catalog_unit_of_work,
)
from app.modules.catalog.exceptions import (
    CatalogItemNotFoundException,
    DuplicateCatalogItemException,
)
from app.modules.catalog.models import CatalogItem, CatalogItemStatus, ItemType
from app.modules.catalog.schemas import (
    CatalogItemCreate,
    CatalogItemListResponse,
    CatalogItemResponse,
    CatalogItemUpdate,
)
from app.modules.catalog.service import CatalogService
from app.modules.identity.dependencies import CurrentUser

router = APIRouter(prefix="/catalog", tags=["Catalog"])

CatalogServiceDependency = Annotated[
    CatalogService,
    Depends(get_catalog_service),
]
CatalogUnitOfWorkDependency = Annotated[
    Any,
    Depends(get_catalog_unit_of_work),
]


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


async def _get_item_for_user(
    uow: Any,
    item_id: uuid.UUID,
    user_id: uuid.UUID,
) -> CatalogItem:
    """Return a catalog item after enforcing business membership."""
    item = await uow.catalog_items.get_by_id(item_id)
    if item is None or not await uow.business_memberships.is_member(
        business_id=item.business_id,
        user_id=user_id,
    ):
        raise CatalogItemNotFoundException(
            "Catalog item not found",
            details={"catalog_item_id": str(item_id)},
        )
    return cast(CatalogItem, item)


@router.post(
    "/items",
    response_model=SuccessResponse[CatalogItemResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create catalog item",
    description="Creates a catalog item for a business the user belongs to.",
    responses={
        HTTPStatus.CREATED: {"description": "Catalog item created successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.BAD_REQUEST: {"model": ErrorResponse},
    },
)
async def create_item(
    request: CatalogItemCreate,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    current_user: CurrentUser,
    uow: CatalogUnitOfWorkDependency,
    service: CatalogServiceDependency,
) -> SuccessResponse[CatalogItemResponse]:
    """Create a catalog item."""
    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)

    item = await service.create(request, business_id)
    return SuccessResponse(
        success=True,
        message="Catalog item created successfully",
        data=item,
    )


@router.get(
    "/items",
    response_model=PaginatedApiResponse[CatalogItemListResponse],
    status_code=status.HTTP_200_OK,
    summary="List catalog items",
    description="Lists catalog items for a business the user belongs to.",
    responses={
        HTTPStatus.OK: {"description": "Catalog items returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
    },
)
async def list_items(
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    current_user: CurrentUser,
    uow: CatalogUnitOfWorkDependency,
    service: CatalogServiceDependency,
    page: Annotated[int, Query(ge=1, description="Page number.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page.")] = 20,
    item_type: Annotated[ItemType | None, Query(description="Filter by item type.")] = None,
    status_filter: Annotated[CatalogItemStatus | None, Query(alias="status", description="Filter by status.")] = None,
) -> PaginatedApiResponse[CatalogItemListResponse]:
    """List catalog items."""
    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)

    item_page = await service.list(
        business_id,
        PaginationParams(page=page, size=page_size),
        item_type=item_type,
        status=status_filter,
    )
    return PaginatedApiResponse(
        success=True,
        message="Catalog items returned successfully",
        data=item_page.items,
        meta=item_page.meta,
    )


@router.get(
    "/items/{item_id}",
    response_model=SuccessResponse[CatalogItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Get catalog item",
    description="Returns a catalog item when the user belongs to its business.",
    responses={
        HTTPStatus.OK: {"description": "Catalog item returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
    },
)
async def get_item(
    item_id: uuid.UUID,
    current_user: CurrentUser,
    uow: CatalogUnitOfWorkDependency,
) -> SuccessResponse[CatalogItemResponse]:
    """Return a catalog item."""
    async with uow:
        item = await _get_item_for_user(uow, item_id, current_user.id)

    return SuccessResponse(
        success=True,
        message="Catalog item returned successfully",
        data=CatalogItemResponse.model_validate(item),
    )


@router.patch(
    "/items/{item_id}",
    response_model=SuccessResponse[CatalogItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Update catalog item",
    description="Updates a catalog item when the user belongs to its business.",
    responses={
        HTTPStatus.OK: {"description": "Catalog item updated successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.BAD_REQUEST: {"model": ErrorResponse},
    },
)
async def update_item(
    item_id: uuid.UUID,
    request: CatalogItemUpdate,
    current_user: CurrentUser,
    uow: CatalogUnitOfWorkDependency,
    service: CatalogServiceDependency,
) -> SuccessResponse[CatalogItemResponse]:
    """Update a catalog item."""
    async with uow:
        item = await _get_item_for_user(uow, item_id, current_user.id)

    updated = await service.update(item_id, request, item.business_id)
    return SuccessResponse(
        success=True,
        message="Catalog item updated successfully",
        data=updated,
    )


@router.post(
    "/items/{item_id}/archive",
    response_model=SuccessResponse[CatalogItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Archive catalog item",
    description="Archives a catalog item when the user belongs to its business.",
    responses={
        HTTPStatus.OK: {"description": "Catalog item archived successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
    },
)
async def archive_item(
    item_id: uuid.UUID,
    current_user: CurrentUser,
    uow: CatalogUnitOfWorkDependency,
    service: CatalogServiceDependency,
) -> SuccessResponse[CatalogItemResponse]:
    """Archive a catalog item."""
    async with uow:
        item = await _get_item_for_user(uow, item_id, current_user.id)

    archived = await service.set_archived(item_id, item.business_id, archived=True)
    return SuccessResponse(
        success=True,
        message="Catalog item archived successfully",
        data=archived,
    )


@router.post(
    "/items/{item_id}/restore",
    response_model=SuccessResponse[CatalogItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Restore catalog item",
    description="Restores an archived catalog item when the user belongs to its business.",
    responses={
        HTTPStatus.OK: {"description": "Catalog item restored successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
    },
)
async def restore_item(
    item_id: uuid.UUID,
    current_user: CurrentUser,
    uow: CatalogUnitOfWorkDependency,
    service: CatalogServiceDependency,
) -> SuccessResponse[CatalogItemResponse]:
    """Restore an archived catalog item."""
    async with uow:
        item = await _get_item_for_user(uow, item_id, current_user.id)

    restored = await service.set_archived(item_id, item.business_id, archived=False)
    return SuccessResponse(
        success=True,
        message="Catalog item restored successfully",
        data=restored,
    )
