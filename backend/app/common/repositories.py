"""Generic async SQLAlchemy repository foundation."""

import uuid
from operator import eq, ge, gt, le, lt, ne
from typing import Any

from sqlalchemy import Select, func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.filters import FilterCondition, FilterParams
from app.common.models.abstract import BaseEntity
from app.common.pagination import Page, PaginationParams


class BaseRepository[ModelT: BaseEntity]:
    """Reusable async repository for SQLAlchemy entities."""

    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        """Initialize the repository with a database session and model class."""
        self.session = session
        self.model = model

    async def get(self, entity_id: uuid.UUID) -> ModelT | None:
        """Return one entity by primary key."""
        return await self.session.get(self.model, entity_id)

    async def add(self, entity: ModelT) -> ModelT:
        """Add an entity to the current session."""
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def list(
        self,
        *,
        pagination: PaginationParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[ModelT]:
        """Return a paginated list of entities."""
        params = pagination or PaginationParams()
        statement = self._apply_filters(select(self.model), filters)
        statement = self._apply_sorting(statement, filters)
        total = await self.count(filters=filters)

        result = await self.session.execute(
            statement.offset(params.offset).limit(params.limit)
        )
        return Page.create(
            items=list(result.scalars().all()),
            total=total,
            params=params,
        )

    async def count(self, *, filters: FilterParams | None = None) -> int:
        """Return a count of entities matching optional filters."""
        statement = self._apply_filters(select(self.model), filters)
        count_statement = select(func.count()).select_from(statement.subquery())
        result = await self.session.execute(count_statement)
        return int(result.scalar_one())

    async def exists(self, entity_id: uuid.UUID) -> bool:
        """Return whether an entity exists by primary key."""
        return await self.get(entity_id) is not None

    async def delete(self, entity: ModelT) -> None:
        """Soft delete an entity in the current session."""
        entity.mark_deleted()
        self.session.add(entity)
        await self.session.flush()

    def _apply_filters(
        self,
        statement: Select[tuple[ModelT]],
        filters: FilterParams | None,
    ) -> Select[tuple[ModelT]]:
        """Apply framework filter conditions to a SQLAlchemy select."""
        if filters is None:
            return statement

        for condition in filters.filters:
            column = self._get_column(condition.field)
            expression = self._build_filter_expression(column, condition)
            statement = statement.where(expression)
        return statement

    def _apply_sorting(
        self,
        statement: Select[tuple[ModelT]],
        filters: FilterParams | None,
    ) -> Select[tuple[ModelT]]:
        """Apply framework sort conditions to a SQLAlchemy select."""
        if filters is None:
            return statement

        for condition in filters.sort:
            column = self._get_column(condition.field)
            statement = statement.order_by(
                column.desc() if condition.direction == "desc" else column.asc()
            )
        return statement

    def _get_column(self, field_name: str) -> Any:
        """Return a mapped column by name."""
        mapper = inspect(self.model)
        if field_name not in mapper.columns:
            raise ValueError(f"Unknown filter field: {field_name}")
        return mapper.columns[field_name]

    def _build_filter_expression(
        self,
        column: Any,
        condition: FilterCondition,
    ) -> Any:
        """Build a SQLAlchemy expression for one filter condition."""
        value = condition.value
        binary_operators = {
            "eq": eq,
            "ne": ne,
            "lt": lt,
            "lte": le,
            "gt": gt,
            "gte": ge,
        }
        if condition.operator in binary_operators:
            return binary_operators[condition.operator](column, value)
        if condition.operator == "like":
            return column.like(str(value))
        if condition.operator == "ilike":
            return column.ilike(str(value))
        values = value if isinstance(value, list) else [value]
        return column.in_(values)
