"""Warehouse repository."""

import uuid
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.filters import FilterParams
from app.common.pagination import Page, PaginationParams
from app.common.repositories import BaseRepository
from app.modules.inventory.models import Warehouse
from app.modules.inventory.schemas import WarehouseCreate, WarehouseUpdate


class WarehouseRepository(BaseRepository[Warehouse]):
    """Repository for warehouse persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, Warehouse)

    async def create(
        self,
        request: WarehouseCreate,
        *,
        business_id: uuid.UUID,
    ) -> Warehouse:
        """Create a warehouse from request data and persistence identifiers."""
        warehouse = Warehouse(**request.model_dump(), business_id=business_id)
        return await self.add(warehouse)

    async def update(
        self,
        warehouse: Warehouse,
        request: WarehouseUpdate,
    ) -> Warehouse:
        """Update mutable warehouse fields from request data."""
        for field_name, value in request.model_dump(exclude_unset=True).items():
            setattr(warehouse, field_name, value)
        self.session.add(warehouse)
        await self.session.flush()
        return warehouse

    async def delete(self, warehouse: Warehouse) -> None:
        """Soft-delete a warehouse."""
        await super().delete(warehouse)

    async def get_by_id(self, warehouse_id: uuid.UUID) -> Warehouse | None:
        """Return a non-deleted warehouse by UUID."""
        statement = self._base_statement().where(Warehouse.id == warehouse_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_code(
        self,
        *,
        business_id: uuid.UUID,
        code: str,
    ) -> Warehouse | None:
        """Return a warehouse by business-scoped code."""
        statement = self._base_statement().where(
            Warehouse.business_id == business_id,
            Warehouse.code == code,
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
        code: str | None = None,
        name: str | None = None,
        is_active: bool | None = None,
    ) -> Page[Warehouse]:
        """Return paginated warehouses with optional filters."""
        statement = self._base_statement().where(Warehouse.business_id == business_id)
        if code is not None:
            statement = statement.where(Warehouse.code == code)
        if name is not None:
            statement = statement.where(Warehouse.name.ilike(f"%{name.strip()}%"))
        if is_active is not None:
            statement = statement.where(Warehouse.is_active.is_(is_active))
        statement = self._apply_filters(statement, filters)
        statement = self._apply_warehouse_sort(statement, sort)
        return await self._paginate(statement, pagination)

    async def search(
        self,
        *,
        business_id: uuid.UUID,
        query: str,
        pagination: PaginationParams | None = None,
    ) -> Page[Warehouse]:
        """Search business warehouses by code or name."""
        search_pattern = f"%{query.strip()}%"
        statement = self._base_statement().where(
            Warehouse.business_id == business_id,
            or_(
                Warehouse.code.ilike(search_pattern),
                Warehouse.name.ilike(search_pattern),
            ),
        )
        statement = self._apply_warehouse_sort(statement, "code")
        return await self._paginate(statement, pagination)

    async def exists(  # type: ignore[override]
        self,
        *,
        business_id: uuid.UUID,
        code: str | None = None,
    ) -> bool:
        """Return whether a warehouse exists for supplied business keys."""
        statement = self._base_statement().where(Warehouse.business_id == business_id)
        if code is not None:
            statement = statement.where(Warehouse.code == code)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none() is not None

    async def _paginate(
        self,
        statement: Select[tuple[Warehouse]],
        pagination: PaginationParams | None,
    ) -> Page[Warehouse]:
        """Paginate a warehouse statement."""
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

    async def _count_statement(self, statement: Select[tuple[Warehouse]]) -> int:
        """Count rows from a selectable statement."""
        count_statement = select(func.count()).select_from(statement.subquery())
        result = await self.session.execute(count_statement)
        return int(result.scalar_one())

    def _base_statement(self) -> Select[tuple[Warehouse]]:
        """Return standard warehouse select."""
        return select(Warehouse).where(Warehouse.is_deleted.is_(False))

    def _apply_warehouse_sort(
        self,
        statement: Select[tuple[Warehouse]],
        sort: str | None,
    ) -> Select[tuple[Warehouse]]:
        """Apply supported warehouse sorting."""
        sort_key = sort or "-created_at"
        direction = "desc" if sort_key.startswith("-") else "asc"
        field_name = sort_key.removeprefix("-")
        sort_columns = {
            "created_at": Warehouse.created_at,
            "code": Warehouse.code,
            "name": Warehouse.name,
        }
        column: Any = sort_columns.get(field_name, Warehouse.created_at)
        return statement.order_by(
            column.desc() if direction == "desc" else column.asc()
        )
