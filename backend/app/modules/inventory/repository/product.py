"""Product repository."""

import uuid
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.filters import FilterParams
from app.common.pagination import Page, PaginationParams
from app.common.repositories import BaseRepository
from app.modules.inventory.models import Product
from app.modules.inventory.schemas import ProductCreate, ProductUpdate


class ProductRepository(BaseRepository[Product]):
    """Repository for product persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, Product)

    async def create(
        self,
        request: ProductCreate,
        *,
        business_id: uuid.UUID,
    ) -> Product:
        """Create a product from request data and persistence identifiers."""
        product = Product(**request.model_dump(), business_id=business_id)
        return await self.add(product)

    async def update(self, product: Product, request: ProductUpdate) -> Product:
        """Update mutable product fields from request data."""
        for field_name, value in request.model_dump(exclude_unset=True).items():
            setattr(product, field_name, value)
        self.session.add(product)
        await self.session.flush()
        return product

    async def delete(self, product: Product) -> None:
        """Soft-delete a product."""
        await super().delete(product)

    async def get_by_id(self, product_id: uuid.UUID) -> Product | None:
        """Return a non-deleted product by UUID."""
        statement = self._base_statement().where(Product.id == product_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_sku(
        self,
        *,
        business_id: uuid.UUID,
        sku: str,
    ) -> Product | None:
        """Return a product by business-scoped SKU."""
        statement = self._base_statement().where(
            Product.business_id == business_id,
            Product.sku == sku,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_barcode(
        self,
        *,
        business_id: uuid.UUID,
        barcode: str,
    ) -> Product | None:
        """Return a product by business-scoped barcode."""
        statement = self._base_statement().where(
            Product.business_id == business_id,
            Product.barcode == barcode,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list(  # type: ignore[override]
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        filters: FilterParams | None = None,
        sort: str | None = None,
        sku: str | None = None,
        name: str | None = None,
        category: str | None = None,
        is_active: bool | None = None,
    ) -> Page[Product]:
        """Return paginated products with optional filters."""
        statement = self._base_statement().where(Product.business_id == business_id)
        if sku is not None:
            statement = statement.where(Product.sku == sku)
        if name is not None:
            statement = statement.where(Product.name.ilike(f"%{name.strip()}%"))
        if category is not None:
            statement = statement.where(Product.category == category)
        if is_active is not None:
            statement = statement.where(Product.is_active.is_(is_active))
        statement = self._apply_filters(statement, filters)
        statement = self._apply_product_sort(statement, sort)
        return await self._paginate(statement, pagination)

    async def search(
        self,
        *,
        business_id: uuid.UUID,
        query: str,
        pagination: PaginationParams | None = None,
    ) -> Page[Product]:
        """Search business products by SKU, barcode, name, or category."""
        search_pattern = f"%{query.strip()}%"
        statement = self._base_statement().where(
            Product.business_id == business_id,
            or_(
                Product.sku.ilike(search_pattern),
                Product.barcode.ilike(search_pattern),
                Product.name.ilike(search_pattern),
                Product.category.ilike(search_pattern),
            ),
        )
        statement = self._apply_product_sort(statement, "sku")
        return await self._paginate(statement, pagination)

    async def exists(  # type: ignore[override]
        self,
        *,
        business_id: uuid.UUID,
        sku: str | None = None,
        barcode: str | None = None,
    ) -> bool:
        """Return whether a product exists for supplied business keys."""
        statement = self._base_statement().where(Product.business_id == business_id)
        if sku is not None:
            statement = statement.where(Product.sku == sku)
        if barcode is not None:
            statement = statement.where(Product.barcode == barcode)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none() is not None

    async def _paginate(
        self,
        statement: Select[tuple[Product]],
        pagination: PaginationParams | None,
    ) -> Page[Product]:
        """Paginate a product statement."""
        params = pagination or PaginationParams()
        total = await self._count_statement(statement)
        result = await self.session.execute(
            statement.offset(params.offset).limit(params.limit)
        )
        return Page.create(
            items=list(result.scalars().all()),
            total=total,
            params=params,
        )

    async def _count_statement(self, statement: Select[tuple[Product]]) -> int:
        """Count rows from a selectable statement."""
        count_statement = select(func.count()).select_from(statement.subquery())
        result = await self.session.execute(count_statement)
        return int(result.scalar_one())

    def _base_statement(self) -> Select[tuple[Product]]:
        """Return standard product select."""
        return select(Product).where(Product.is_deleted.is_(False))

    def _apply_product_sort(
        self,
        statement: Select[tuple[Product]],
        sort: str | None,
    ) -> Select[tuple[Product]]:
        """Apply supported product sorting."""
        sort_key = sort or "-created_at"
        direction = "desc" if sort_key.startswith("-") else "asc"
        field_name = sort_key.removeprefix("-")
        sort_columns = {
            "created_at": Product.created_at,
            "sku": Product.sku,
            "name": Product.name,
        }
        column: Any = sort_columns.get(field_name, Product.created_at)
        return statement.order_by(
            column.desc() if direction == "desc" else column.asc()
        )
