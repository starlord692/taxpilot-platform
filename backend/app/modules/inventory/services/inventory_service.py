"""Inventory read service."""

import uuid
from collections.abc import Callable
from typing import Protocol

from app.common.pagination import Page, PaginationParams
from app.modules.inventory.exceptions import StockBalanceNotFoundException
from app.modules.inventory.models import Product, StockBalance
from app.modules.inventory.schemas import (
    ProductListResponse,
    StockBalanceListResponse,
    StockBalanceResponse,
)


class InventoryProductRepository(Protocol):
    """Product repository behavior required by inventory read service."""

    async def search(
        self,
        *,
        business_id: uuid.UUID,
        query: str,
        pagination: PaginationParams | None = None,
    ) -> Page[Product]:
        """Search products for a business."""
        ...


class InventoryStockBalanceRepository(Protocol):
    """Stock balance repository behavior required by inventory read service."""

    async def get_by_id(self, balance_id: uuid.UUID) -> StockBalance | None:
        """Return a stock balance by UUID."""
        ...

    async def get_by_product(
        self,
        *,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> list[StockBalance]:
        """Return stock balances for a product."""
        ...

    async def get_by_product_and_warehouse(
        self,
        *,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
    ) -> StockBalance | None:
        """Return one stock balance for a product and warehouse."""
        ...

    async def list(
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        product_id: uuid.UUID | None = None,
        warehouse_id: uuid.UUID | None = None,
    ) -> Page[StockBalance]:
        """Return stock balances for a business."""
        ...


class InventoryUnitOfWork(Protocol):
    """Unit of Work contract required by inventory read service."""

    products: InventoryProductRepository
    stock_balances: InventoryStockBalanceRepository

    async def __aenter__(self) -> "InventoryUnitOfWork":
        """Enter the inventory read transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the inventory read transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit read transaction."""
        ...


UnitOfWorkFactory = Callable[[], InventoryUnitOfWork]


class InventoryService:
    """Coordinate inventory read operations."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        """Initialize service dependencies."""
        self._unit_of_work_factory = unit_of_work_factory

    async def get_stock_balance(
        self,
        balance_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
    ) -> StockBalanceResponse:
        """Return a stock balance by UUID within a business."""
        async with self._unit_of_work_factory() as uow:
            balance = await uow.stock_balances.get_by_id(balance_id)
            if balance is None or balance.business_id != business_id:
                raise StockBalanceNotFoundException(
                    "Stock balance not found",
                    details={"balance_id": str(balance_id)},
                )
            await uow.commit()
        return StockBalanceResponse.model_validate(balance)

    async def list_stock_balances(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        product_id: uuid.UUID | None = None,
        warehouse_id: uuid.UUID | None = None,
    ) -> Page[StockBalanceListResponse]:
        """Return paginated stock balances for a business."""
        async with self._unit_of_work_factory() as uow:
            page = await uow.stock_balances.list(
                business_id=business_id,
                pagination=pagination,
                product_id=product_id,
                warehouse_id=warehouse_id,
            )
            await uow.commit()
        return self._balance_page_to_response(page, pagination)

    async def get_product_stock(
        self,
        product_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
    ) -> list[StockBalanceResponse]:
        """Return stock balances for a product."""
        async with self._unit_of_work_factory() as uow:
            balances = await uow.stock_balances.get_by_product(
                business_id=business_id,
                product_id=product_id,
            )
            await uow.commit()
        return [
            StockBalanceResponse.model_validate(balance)
            for balance in balances
        ]

    async def get_warehouse_stock(
        self,
        warehouse_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
    ) -> Page[StockBalanceListResponse]:
        """Return stock balances for a warehouse."""
        return await self.list_stock_balances(
            business_id,
            pagination,
            warehouse_id=warehouse_id,
        )

    async def search_inventory(
        self,
        business_id: uuid.UUID,
        query: str,
        pagination: PaginationParams | None = None,
    ) -> Page[ProductListResponse]:
        """Search inventory products for a business."""
        async with self._unit_of_work_factory() as uow:
            page = await uow.products.search(
                business_id=business_id,
                query=query,
                pagination=pagination,
            )
            await uow.commit()
        return Page.create(
            items=[
                ProductListResponse.model_validate(product)
                for product in page.items
            ],
            total=page.meta.total,
            params=pagination or PaginationParams(),
        )

    def _balance_page_to_response(
        self,
        page: Page[StockBalance],
        pagination: PaginationParams | None,
    ) -> Page[StockBalanceListResponse]:
        """Convert stock balance page to response page."""
        return Page.create(
            items=[
                StockBalanceListResponse.model_validate(balance)
                for balance in page.items
            ],
            total=page.meta.total,
            params=pagination or PaginationParams(),
        )
