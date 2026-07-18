"""Product service."""

import uuid
from collections.abc import Callable
from decimal import Decimal
from typing import Protocol

from app.common.events import EventDispatcher
from app.common.pagination import Page, PaginationParams
from app.modules.inventory.events import (
    ProductActivatedEvent,
    ProductCreatedEvent,
    ProductDeactivatedEvent,
    ProductUpdatedEvent,
)
from app.modules.inventory.exceptions import (
    ActiveStockExistsException,
    DuplicateProductException,
    ProductActiveException,
    ProductInactiveException,
    ProductNotFoundException,
)
from app.modules.inventory.models import Product, StockBalance
from app.modules.inventory.schemas import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)

ZERO_QUANTITY = Decimal("0.0000")


class ProductPersistenceRepository(Protocol):
    """Product repository behavior required by product service."""

    async def create(
        self,
        request: ProductCreate,
        *,
        business_id: uuid.UUID,
    ) -> Product:
        """Create a product."""
        ...

    async def get_by_id(self, product_id: uuid.UUID) -> Product | None:
        """Return a product by UUID."""
        ...

    async def get_by_sku(
        self,
        *,
        business_id: uuid.UUID,
        sku: str,
    ) -> Product | None:
        """Return a product by SKU."""
        ...

    async def get_by_barcode(
        self,
        *,
        business_id: uuid.UUID,
        barcode: str,
    ) -> Product | None:
        """Return a product by barcode."""
        ...

    async def list(
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        sort: str | None = None,
        sku: str | None = None,
        name: str | None = None,
        category: str | None = None,
        is_active: bool | None = None,
    ) -> Page[Product]:
        """Return products for a business."""
        ...

    async def search(
        self,
        *,
        business_id: uuid.UUID,
        query: str,
        pagination: PaginationParams | None = None,
    ) -> Page[Product]:
        """Search products for a business."""
        ...

    async def update(self, product: Product, request: ProductUpdate) -> Product:
        """Update a product."""
        ...


class ProductStockBalanceRepository(Protocol):
    """Stock balance repository behavior required by product service."""

    async def get_by_product(
        self,
        *,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> list[StockBalance]:
        """Return stock balances for a product."""
        ...


class ProductUnitOfWork(Protocol):
    """Unit of Work contract required by product service."""

    products: ProductPersistenceRepository
    stock_balances: ProductStockBalanceRepository

    async def __aenter__(self) -> "ProductUnitOfWork":
        """Enter the product transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the product transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit product changes."""
        ...


UnitOfWorkFactory = Callable[[], ProductUnitOfWork]


class ProductService:
    """Coordinate product lifecycle operations."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
    ) -> None:
        """Initialize service dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher

    async def create_product(
        self,
        request: ProductCreate,
        *,
        business_id: uuid.UUID,
    ) -> ProductResponse:
        """Create a product and publish an event."""
        validated_request = ProductCreate.model_validate(request)
        async with self._unit_of_work_factory() as uow:
            await self._ensure_unique_product(
                uow,
                business_id=business_id,
                sku=validated_request.sku,
                barcode=validated_request.barcode,
            )
            product = await uow.products.create(
                validated_request,
                business_id=business_id,
            )
            await self._event_dispatcher.dispatch(
                ProductCreatedEvent(
                    product_id=product.id,
                    business_id=product.business_id,
                )
            )
            await uow.commit()
        return ProductResponse.model_validate(product)

    async def update_product(
        self,
        product_id: uuid.UUID,
        request: ProductUpdate,
        *,
        business_id: uuid.UUID,
    ) -> ProductResponse:
        """Update a product and publish an event."""
        validated_request = ProductUpdate.model_validate(request)
        async with self._unit_of_work_factory() as uow:
            product = await self._get_existing_product(uow, product_id, business_id)
            await self._ensure_unique_product(
                uow,
                business_id=business_id,
                sku=validated_request.sku,
                barcode=validated_request.barcode,
                current_product_id=product.id,
            )
            product = await uow.products.update(product, validated_request)
            await self._event_dispatcher.dispatch(
                ProductUpdatedEvent(
                    product_id=product.id,
                    business_id=product.business_id,
                )
            )
            await uow.commit()
        return ProductResponse.model_validate(product)

    async def deactivate_product(
        self,
        product_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
    ) -> ProductResponse:
        """Deactivate a product when no active stock remains."""
        async with self._unit_of_work_factory() as uow:
            product = await self._get_existing_product(uow, product_id, business_id)
            if not product.is_active:
                raise ProductInactiveException(
                    "Product is already inactive",
                    details={"product_id": str(product_id)},
                )
            await self._ensure_no_active_stock(uow, product)
            product = await uow.products.update(product, ProductUpdate(is_active=False))
            await self._event_dispatcher.dispatch(
                ProductDeactivatedEvent(
                    product_id=product.id,
                    business_id=product.business_id,
                )
            )
            await uow.commit()
        return ProductResponse.model_validate(product)

    async def activate_product(
        self,
        product_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
    ) -> ProductResponse:
        """Activate a product and publish an event."""
        async with self._unit_of_work_factory() as uow:
            product = await self._get_existing_product(uow, product_id, business_id)
            if product.is_active:
                raise ProductActiveException(
                    "Product is already active",
                    details={"product_id": str(product_id)},
                )
            product = await uow.products.update(product, ProductUpdate(is_active=True))
            await self._event_dispatcher.dispatch(
                ProductActivatedEvent(
                    product_id=product.id,
                    business_id=product.business_id,
                )
            )
            await uow.commit()
        return ProductResponse.model_validate(product)

    async def get_product(
        self,
        product_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
    ) -> ProductResponse:
        """Return a product by UUID within a business."""
        async with self._unit_of_work_factory() as uow:
            product = await self._get_existing_product(uow, product_id, business_id)
            await uow.commit()
        return ProductResponse.model_validate(product)

    async def list_products(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        sort: str | None = None,
        sku: str | None = None,
        name: str | None = None,
        category: str | None = None,
        is_active: bool | None = None,
    ) -> Page[ProductListResponse]:
        """Return paginated products for a business."""
        async with self._unit_of_work_factory() as uow:
            page = await uow.products.list(
                business_id=business_id,
                pagination=pagination,
                sort=sort,
                sku=sku,
                name=name,
                category=category,
                is_active=is_active,
            )
            await uow.commit()
        return self._product_page_to_response(page, pagination)

    async def search_products(
        self,
        business_id: uuid.UUID,
        query: str,
        pagination: PaginationParams | None = None,
    ) -> Page[ProductListResponse]:
        """Search products for a business."""
        async with self._unit_of_work_factory() as uow:
            page = await uow.products.search(
                business_id=business_id,
                query=query,
                pagination=pagination,
            )
            await uow.commit()
        return self._product_page_to_response(page, pagination)

    async def _get_existing_product(
        self,
        uow: ProductUnitOfWork,
        product_id: uuid.UUID,
        business_id: uuid.UUID,
    ) -> Product:
        """Return a product or raise not found."""
        product = await uow.products.get_by_id(product_id)
        if product is None or product.business_id != business_id:
            raise ProductNotFoundException(
                "Product not found",
                details={"product_id": str(product_id)},
            )
        return product

    async def _ensure_unique_product(
        self,
        uow: ProductUnitOfWork,
        *,
        business_id: uuid.UUID,
        sku: str | None,
        barcode: str | None,
        current_product_id: uuid.UUID | None = None,
    ) -> None:
        """Validate product SKU and barcode uniqueness within a business."""
        if sku is not None:
            existing = await uow.products.get_by_sku(
                business_id=business_id,
                sku=sku,
            )
            if existing is not None and existing.id != current_product_id:
                raise DuplicateProductException(
                    "Product SKU already exists for this business",
                    details={"business_id": str(business_id), "sku": sku},
                )
        if barcode is not None:
            existing = await uow.products.get_by_barcode(
                business_id=business_id,
                barcode=barcode,
            )
            if existing is not None and existing.id != current_product_id:
                raise DuplicateProductException(
                    "Product barcode already exists for this business",
                    details={"business_id": str(business_id), "barcode": barcode},
                )

    async def _ensure_no_active_stock(
        self,
        uow: ProductUnitOfWork,
        product: Product,
    ) -> None:
        """Raise when product has stock on hand."""
        balances = await uow.stock_balances.get_by_product(
            business_id=product.business_id,
            product_id=product.id,
        )
        if any(balance.quantity_on_hand > ZERO_QUANTITY for balance in balances):
            raise ActiveStockExistsException(
                "Product cannot be deactivated while stock exists",
                details={"product_id": str(product.id)},
            )

    def _product_page_to_response(
        self,
        page: Page[Product],
        pagination: PaginationParams | None,
    ) -> Page[ProductListResponse]:
        """Convert product page to response page."""
        return Page.create(
            items=[
                ProductListResponse.model_validate(product)
                for product in page.items
            ],
            total=page.meta.total,
            params=pagination or PaginationParams(),
        )
