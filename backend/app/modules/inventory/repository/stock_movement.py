"""Stock movement repository."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.filters import FilterParams
from app.common.pagination import Page, PaginationParams
from app.common.repositories import BaseRepository
from app.modules.inventory.models import MovementType, StockMovement
from app.modules.inventory.schemas import StockMovementCreate


class StockMovementRepository(BaseRepository[StockMovement]):
    """Repository for stock movement persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, StockMovement)

    async def create(
        self,
        request: StockMovementCreate,
        *,
        business_id: uuid.UUID,
    ) -> StockMovement:
        """Create a stock movement from request data and persistence identifiers."""
        movement = StockMovement(**request.model_dump(), business_id=business_id)
        return await self.add(movement)

    async def get_by_id(self, movement_id: uuid.UUID) -> StockMovement | None:
        """Return a non-deleted stock movement by UUID."""
        statement = self._base_statement().where(StockMovement.id == movement_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list(  # type: ignore[override]
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        filters: FilterParams | None = None,
        sort: str | None = None,
        product_id: uuid.UUID | None = None,
        warehouse_id: uuid.UUID | None = None,
        movement_type: MovementType | None = None,
        created_at_from: datetime | None = None,
        created_at_to: datetime | None = None,
    ) -> Page[StockMovement]:
        """Return paginated stock movements with optional filters."""
        statement = self._base_statement().where(
            StockMovement.business_id == business_id
        )
        statement = self._apply_optional_filters(
            statement,
            product_id=product_id,
            warehouse_id=warehouse_id,
            movement_type=movement_type,
            created_at_from=created_at_from,
            created_at_to=created_at_to,
        )
        statement = self._apply_filters(statement, filters)
        statement = self._apply_movement_sort(statement, sort)
        return await self._paginate(statement, pagination)

    async def list_by_product(
        self,
        *,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
        pagination: PaginationParams | None = None,
    ) -> Page[StockMovement]:
        """Return paginated stock movements for a product."""
        return await self.list(
            business_id=business_id,
            product_id=product_id,
            pagination=pagination,
        )

    async def list_by_warehouse(
        self,
        *,
        business_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        pagination: PaginationParams | None = None,
    ) -> Page[StockMovement]:
        """Return paginated stock movements for a warehouse."""
        return await self.list(
            business_id=business_id,
            warehouse_id=warehouse_id,
            pagination=pagination,
        )

    async def list_by_reference(
        self,
        *,
        business_id: uuid.UUID,
        reference_type: str,
        reference_id: uuid.UUID,
        pagination: PaginationParams | None = None,
    ) -> Page[StockMovement]:
        """Return paginated stock movements for a source reference."""
        statement = self._base_statement().where(
            StockMovement.business_id == business_id,
            StockMovement.reference_type == reference_type,
            StockMovement.reference_id == reference_id,
        )
        statement = self._apply_movement_sort(statement, "-created_at")
        return await self._paginate(statement, pagination)

    async def _paginate(
        self,
        statement: Select[tuple[StockMovement]],
        pagination: PaginationParams | None,
    ) -> Page[StockMovement]:
        """Paginate a stock movement statement."""
        params = pagination or PaginationParams()
        total = await self._count_statement(statement)
        result = await self.session.execute(
            statement.offset(params.offset).limit(params.limit)
        )
        return Page.create(
            items=list(result.scalars().unique().all()),
            total=total,
            params=params,
        )

    async def _count_statement(self, statement: Select[tuple[StockMovement]]) -> int:
        """Count rows from a selectable statement."""
        count_statement = select(func.count()).select_from(statement.subquery())
        result = await self.session.execute(count_statement)
        return int(result.scalar_one())

    def _base_statement(self) -> Select[tuple[StockMovement]]:
        """Return standard stock movement select with relationships loaded."""
        return (
            select(StockMovement)
            .options(
                selectinload(StockMovement.product),
                selectinload(StockMovement.warehouse),
            )
            .where(StockMovement.is_deleted.is_(False))
        )

    def _apply_optional_filters(
        self,
        statement: Select[tuple[StockMovement]],
        *,
        product_id: uuid.UUID | None,
        warehouse_id: uuid.UUID | None,
        movement_type: MovementType | None,
        created_at_from: datetime | None,
        created_at_to: datetime | None,
    ) -> Select[tuple[StockMovement]]:
        """Apply explicit stock movement filter options."""
        if product_id is not None:
            statement = statement.where(StockMovement.product_id == product_id)
        if warehouse_id is not None:
            statement = statement.where(StockMovement.warehouse_id == warehouse_id)
        if movement_type is not None:
            statement = statement.where(StockMovement.movement_type == movement_type)
        if created_at_from is not None:
            statement = statement.where(StockMovement.created_at >= created_at_from)
        if created_at_to is not None:
            statement = statement.where(StockMovement.created_at <= created_at_to)
        return statement

    def _apply_movement_sort(
        self,
        statement: Select[tuple[StockMovement]],
        sort: str | None,
    ) -> Select[tuple[StockMovement]]:
        """Apply supported stock movement sorting."""
        sort_key = sort or "-created_at"
        direction = "desc" if sort_key.startswith("-") else "asc"
        field_name = sort_key.removeprefix("-")
        sort_columns = {
            "created_at": StockMovement.created_at,
        }
        column: Any = sort_columns.get(field_name, StockMovement.created_at)
        return statement.order_by(
            column.desc() if direction == "desc" else column.asc()
        )
