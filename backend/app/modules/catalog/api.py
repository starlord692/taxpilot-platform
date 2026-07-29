"""Canonical catalog API."""

import uuid
from collections.abc import Callable
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Query
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.events import EventDispatcher
from app.common.pagination import PaginationParams
from app.common.unit_of_work import SQLAlchemyUnitOfWork
from app.core.database import database_state, initialize_database
from app.core.responses import PaginatedApiResponse, SuccessResponse
from app.modules.business.api.context import ensure_active_business_membership
from app.modules.catalog.models import CatalogItemStatus, ItemType
from app.modules.catalog.schemas import (
    CatalogItemCreate,
    CatalogItemListResponse,
    CatalogItemResponse,
    CatalogItemUpdate,
)
from app.modules.catalog.service import CatalogService, CatalogUnitOfWork
from app.modules.identity.dependencies import CurrentUser

router = APIRouter(prefix="/catalog/items", tags=["Catalog"])


def get_session_factory() -> Callable[[], AsyncSession]:
    if database_state.session_factory is None:
        initialize_database()
    if database_state.session_factory is None:
        raise RuntimeError("Database session factory is not initialized")
    return database_state.session_factory


def get_catalog_service() -> CatalogService:
    factory = get_session_factory()
    return CatalogService(
        cast(Callable[[], CatalogUnitOfWork], lambda: SQLAlchemyUnitOfWork(factory)),
        EventDispatcher(),
    )


Service = Annotated[CatalogService, Depends(get_catalog_service)]


async def member(business_id: uuid.UUID, user_id: uuid.UUID, service_uow: Any) -> None:
    async with service_uow as uow:
        await ensure_active_business_membership(
            uow,
            business_id=business_id,
            user_id=user_id,
            entered=True,
        )


@router.post(
    "",
    response_model=SuccessResponse[CatalogItemResponse],
    status_code=http_status.HTTP_201_CREATED,
)
async def create_item(
    request: CatalogItemCreate,
    current_user: CurrentUser,
    service: Service,
    business_id: Annotated[uuid.UUID, Query()],
) -> SuccessResponse[CatalogItemResponse]:
    await member(
        business_id,
        current_user.id,
        SQLAlchemyUnitOfWork(get_session_factory()),
    )
    return SuccessResponse(
        success=True,
        message="Catalog item created successfully",
        data=await service.create(request, business_id),
    )


@router.get("", response_model=PaginatedApiResponse[CatalogItemListResponse])
async def list_items(
    current_user: CurrentUser,
    service: Service,
    business_id: Annotated[uuid.UUID, Query()],
    page: int = 1,
    page_size: int = 20,
    item_type: ItemType | None = None,
    status: CatalogItemStatus | None = None,
) -> PaginatedApiResponse[CatalogItemListResponse]:
    await member(
        business_id,
        current_user.id,
        SQLAlchemyUnitOfWork(get_session_factory()),
    )
    result = await service.list(
        business_id, PaginationParams(page=page, size=page_size), item_type, status
    )
    return PaginatedApiResponse(
        success=True,
        message="Catalog items returned successfully",
        data=result.items,
        meta=result.meta,
    )


@router.get("/{item_id}", response_model=SuccessResponse[CatalogItemResponse])
async def get_item(
    item_id: uuid.UUID,
    current_user: CurrentUser,
    service: Service,
    business_id: Annotated[uuid.UUID, Query()],
) -> SuccessResponse[CatalogItemResponse]:
    await member(
        business_id,
        current_user.id,
        SQLAlchemyUnitOfWork(get_session_factory()),
    )
    return SuccessResponse(
        success=True,
        message="Catalog item returned successfully",
        data=await service.get(item_id, business_id),
    )


@router.patch("/{item_id}", response_model=SuccessResponse[CatalogItemResponse])
async def update_item(
    item_id: uuid.UUID,
    request: CatalogItemUpdate,
    current_user: CurrentUser,
    service: Service,
    business_id: Annotated[uuid.UUID, Query()],
) -> SuccessResponse[CatalogItemResponse]:
    await member(
        business_id,
        current_user.id,
        SQLAlchemyUnitOfWork(get_session_factory()),
    )
    return SuccessResponse(
        success=True,
        message="Catalog item updated successfully",
        data=await service.update(item_id, request, business_id),
    )


@router.post("/{item_id}/archive", response_model=SuccessResponse[CatalogItemResponse])
async def archive_item(
    item_id: uuid.UUID,
    current_user: CurrentUser,
    service: Service,
    business_id: Annotated[uuid.UUID, Query()],
) -> SuccessResponse[CatalogItemResponse]:
    await member(
        business_id,
        current_user.id,
        SQLAlchemyUnitOfWork(get_session_factory()),
    )
    return SuccessResponse(
        success=True,
        message="Catalog item archived successfully",
        data=await service.set_archived(item_id, business_id, True),
    )


@router.post("/{item_id}/restore", response_model=SuccessResponse[CatalogItemResponse])
async def restore_item(
    item_id: uuid.UUID,
    current_user: CurrentUser,
    service: Service,
    business_id: Annotated[uuid.UUID, Query()],
) -> SuccessResponse[CatalogItemResponse]:
    await member(
        business_id,
        current_user.id,
        SQLAlchemyUnitOfWork(get_session_factory()),
    )
    return SuccessResponse(
        success=True,
        message="Catalog item restored successfully",
        data=await service.set_archived(item_id, business_id, False),
    )
