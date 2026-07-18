"""Inventory product API router."""

import uuid
from http import HTTPStatus
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Query, status

from app.common.pagination import PaginationParams
from app.core.responses import ErrorResponse, PaginatedApiResponse, SuccessResponse
from app.modules.business.exceptions import BusinessNotMemberException
from app.modules.identity.dependencies import CurrentUser
from app.modules.inventory.api.dependencies import (
    get_inventory_unit_of_work,
    get_product_service,
)
from app.modules.inventory.exceptions import ProductNotFoundException
from app.modules.inventory.models import Product
from app.modules.inventory.schemas import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from app.modules.inventory.services import ProductService

router = APIRouter(prefix="/inventory/products", tags=["Inventory Products"])
ProductServiceDependency = Annotated[ProductService, Depends(get_product_service)]
InventoryUnitOfWorkDependency = Annotated[Any, Depends(get_inventory_unit_of_work)]


@router.post(
    "",
    response_model=SuccessResponse[ProductResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create product",
    description="Creates an inventory product for a business member.",
    responses={
        HTTPStatus.CREATED: {"description": "Product created successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def create_product(
    request: ProductCreate,
    current_user: CurrentUser,
    uow: InventoryUnitOfWorkDependency,
    product_service: ProductServiceDependency,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[ProductResponse]:
    """Create an inventory product."""
    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)

    product = await product_service.create_product(request, business_id=business_id)
    return SuccessResponse(
        success=True,
        message="Product created successfully",
        data=product,
    )


@router.get(
    "",
    response_model=PaginatedApiResponse[ProductListResponse],
    status_code=status.HTTP_200_OK,
    summary="List products",
    description="Lists inventory products for a business member.",
    responses={
        HTTPStatus.OK: {"description": "Products returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
    },
)
async def list_products(
    current_user: CurrentUser,
    uow: InventoryUnitOfWorkDependency,
    product_service: ProductServiceDependency,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    page: Annotated[int, Query(ge=1, description="Page number.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page.")] = 20,
    sku: Annotated[str | None, Query(description="Filter by SKU.")] = None,
    name: Annotated[str | None, Query(description="Filter by product name.")] = None,
    category: Annotated[str | None, Query(description="Filter by category.")] = None,
    active: Annotated[bool | None, Query(description="Filter by active flag.")] = None,
    sort: Annotated[
        str | None,
        Query(description="Sort field, e.g. sku, name, -created_at."),
    ] = None,
) -> PaginatedApiResponse[ProductListResponse]:
    """List inventory products."""
    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)

    product_page = await product_service.list_products(
        business_id,
        PaginationParams(page=page, size=page_size),
        sort=sort,
        sku=sku,
        name=name,
        category=category,
        is_active=active,
    )
    return PaginatedApiResponse(
        success=True,
        message="Products returned successfully",
        data=product_page.items,
        meta=product_page.meta,
    )


@router.get(
    "/{product_id}",
    response_model=SuccessResponse[ProductResponse],
    status_code=status.HTTP_200_OK,
    summary="Get product",
    description=(
        "Returns a product when the authenticated user belongs to its business."
    ),
    responses={
        HTTPStatus.OK: {"description": "Product returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
    },
)
async def get_product(
    product_id: uuid.UUID,
    current_user: CurrentUser,
    uow: InventoryUnitOfWorkDependency,
    product_service: ProductServiceDependency,
) -> SuccessResponse[ProductResponse]:
    """Return an inventory product."""
    async with uow:
        product = await _get_product_for_user(uow, product_id, current_user.id)

    product_response = await product_service.get_product(
        product_id,
        business_id=product.business_id,
    )
    return SuccessResponse(
        success=True,
        message="Product returned successfully",
        data=product_response,
    )


@router.patch(
    "/{product_id}",
    response_model=SuccessResponse[ProductResponse],
    status_code=status.HTTP_200_OK,
    summary="Update product",
    description=(
        "Updates a product when the authenticated user belongs to its business."
    ),
    responses={
        HTTPStatus.OK: {"description": "Product updated successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def update_product(
    product_id: uuid.UUID,
    request: ProductUpdate,
    current_user: CurrentUser,
    uow: InventoryUnitOfWorkDependency,
    product_service: ProductServiceDependency,
) -> SuccessResponse[ProductResponse]:
    """Update an inventory product."""
    async with uow:
        product = await _get_product_for_user(uow, product_id, current_user.id)

    product_response = await product_service.update_product(
        product_id,
        request,
        business_id=product.business_id,
    )
    return SuccessResponse(
        success=True,
        message="Product updated successfully",
        data=product_response,
    )


@router.post(
    "/{product_id}/activate",
    response_model=SuccessResponse[ProductResponse],
    status_code=status.HTTP_200_OK,
    summary="Activate product",
    description=(
        "Activates a product when the authenticated user belongs to its business."
    ),
    responses={
        HTTPStatus.OK: {"description": "Product activated successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
    },
)
async def activate_product(
    product_id: uuid.UUID,
    current_user: CurrentUser,
    uow: InventoryUnitOfWorkDependency,
    product_service: ProductServiceDependency,
) -> SuccessResponse[ProductResponse]:
    """Activate an inventory product."""
    async with uow:
        product = await _get_product_for_user(uow, product_id, current_user.id)

    product_response = await product_service.activate_product(
        product_id,
        business_id=product.business_id,
    )
    return SuccessResponse(
        success=True,
        message="Product activated successfully",
        data=product_response,
    )


@router.post(
    "/{product_id}/deactivate",
    response_model=SuccessResponse[ProductResponse],
    status_code=status.HTTP_200_OK,
    summary="Deactivate product",
    description=(
        "Deactivates a product when the authenticated user belongs to its business."
    ),
    responses={
        HTTPStatus.OK: {"description": "Product deactivated successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
    },
)
async def deactivate_product(
    product_id: uuid.UUID,
    current_user: CurrentUser,
    uow: InventoryUnitOfWorkDependency,
    product_service: ProductServiceDependency,
) -> SuccessResponse[ProductResponse]:
    """Deactivate an inventory product."""
    async with uow:
        product = await _get_product_for_user(uow, product_id, current_user.id)

    product_response = await product_service.deactivate_product(
        product_id,
        business_id=product.business_id,
    )
    return SuccessResponse(
        success=True,
        message="Product deactivated successfully",
        data=product_response,
    )


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


async def _get_product_for_user(
    uow: Any,
    product_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Product:
    """Return a product after enforcing business membership."""
    product = await uow.products.get_by_id(product_id)
    if product is None:
        raise ProductNotFoundException(
            "Product not found",
            details={"product_id": str(product_id)},
        )
    await _ensure_business_member(uow, product.business_id, user_id)
    return cast(Product, product)
